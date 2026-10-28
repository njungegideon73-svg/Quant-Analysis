package ta;

import com.dukascopy.api.*;
import com.dukascopy.api.system.ISystemListener;
import com.dukascopy.api.system.ITesterClient;
import com.dukascopy.api.system.TesterFactory;

import java.io.PrintWriter;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;

/**
 * Replay engine orders in Dukascopy's historical tester (all ticks), one order per tester run.
 * Args: orders.csv out.csv   Env: DUKASCOPY_USER, DUKASCOPY_PASSWORD, optional DUKASCOPY_JNLP.
 * orders.csv: id,pair,dir,entry,stop,target,from_ms,to_ms,windows,flats
 *   windows = "a-b;c-d" epoch-ms spans when the engine's order is live (placed and inside the session);
 *   flats = "t1;t2" Friday 16:30 NY closes. The limit is working only inside a window, as in the engine.
 * out.csv: id,fill_ms,fill_px,exit_ms,exit_px,reason (sl | tp | flat | cancelled | open | rejected:... | data_gap)
 * Ticks are downloaded first and retried until the tester reports them complete; a feed hole would otherwise
 * look like a late fill.
 */
public class OrderReplay {
    static volatile CountDownLatch done;
    static volatile boolean allLoaded;

    static final LoadingProgressListener PROGRESS = new LoadingProgressListener() {
        public void dataLoaded(long s, long e, long c, String i) {}
        public void loadingFinished(boolean all, long s, long e, long c) { allLoaded = all; }
        public boolean stopJob() { return false; }
    };

    public static void main(String[] args) throws Exception {
        try {
            run(args);
        } finally {
            System.exit(0);  // an SDK thread is non-daemon: without this a failed run leaves the JVM (and our caller) hanging
        }
    }

    static void connect(ITesterClient tester, String jnlp) throws Exception {
        tester.connect(jnlp, System.getenv("DUKASCOPY_USER"), System.getenv("DUKASCOPY_PASSWORD"));
        for (int i = 0; i < 60 && !tester.isConnected(); i++) Thread.sleep(1000);
    }

    static void run(String[] args) throws Exception {
        List<String> lines = Files.readAllLines(Paths.get(args[0]));
        ITesterClient tester = TesterFactory.getDefaultInstance();
        tester.setSystemListener(new ISystemListener() {
            public void onStart(long id) {}
            public void onStop(long id) { done.countDown(); }
            public void onConnect() {}
            public void onDisconnect() {}
        });
        String jnlp = System.getenv().getOrDefault("DUKASCOPY_JNLP", "https://platform.dukascopy.com/demo/jforex.jnlp");
        connect(tester, jnlp);
        if (!tester.isConnected()) {
            System.out.println("ERROR could not connect to JForex demo (check login in .env)");
            return;
        }
        tester.setInitialDeposit(JFCurrency.getInstance("USD"), 50_000);
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(Paths.get(args[1])))) {
            w.println("id,fill_ms,fill_px,exit_ms,exit_px,reason");
            for (String line : lines.subList(1, lines.size())) {
                Replay r = new Replay(line.split(",", -1));
                try {
                    if (!tester.isConnected()) connect(tester, jnlp);  // Dukascopy drops long sessions
                    tester.setSubscribedInstruments(Set.of(r.ins));
                    tester.setDataInterval(ITesterClient.DataLoadingMethod.ALL_TICKS, r.from, r.to);
                    allLoaded = false;
                    for (int k = 0; k < 6 && !allLoaded; k++) {  // the public feed answers 503 under load
                        if (k > 0) Thread.sleep(30_000L * k);
                        tester.downloadData(PROGRESS).get();
                    }
                    if (allLoaded) {
                        done = new CountDownLatch(1);
                        long pid = tester.startStrategy(r, PROGRESS);
                        if (!done.await(10, java.util.concurrent.TimeUnit.MINUTES)) {  // a dropped feed stalls the tester
                            r.reason = "error:timeout";
                            tester.stopStrategy(pid);
                            done.await(1, java.util.concurrent.TimeUnit.MINUTES);
                        }
                    } else {
                        r.reason = "data_gap";
                    }
                } catch (Exception e) {
                    r.reason = "error:" + e.getClass().getSimpleName();
                }
                w.println(r.id + "," + r.fillMs + "," + r.fillPx + "," + r.exitMs + "," + r.exitPx + "," + r.reason);
                w.flush();
                System.out.println("DONE " + r.id + " " + r.reason);
                System.out.flush();
            }
        }
        System.exit(0);
    }

    static class Replay implements IStrategy {
        final String id;
        final Instrument ins;
        final int dir;
        final double entry, stop, target;
        final long from, to;
        final long[][] windows;
        final long[] flats;
        IContext ctx;
        IOrder order;
        int submits;
        long fillMs = -1, exitMs = -1, nextFlat = Long.MAX_VALUE;
        double fillPx = Double.NaN, exitPx = Double.NaN;
        String reason = "open";

        Replay(String[] f) {
            id = f[0];
            ins = Instrument.fromString(f[1].substring(0, 3) + "/" + f[1].substring(3));
            dir = Integer.parseInt(f[2]);
            entry = Double.parseDouble(f[3]);
            stop = Double.parseDouble(f[4]);
            target = Double.parseDouble(f[5]);
            from = Long.parseLong(f[6]);
            to = Long.parseLong(f[7]);
            windows = Arrays.stream(f[8].split(";")).map(s -> Arrays.stream(s.split("-")).mapToLong(Long::parseLong).toArray())
                    .toArray(long[][]::new);
            flats = f[9].isEmpty() ? new long[0] : Arrays.stream(f[9].split(";")).mapToLong(Long::parseLong).toArray();
        }

        double grid(double px) {
            return new BigDecimal(Double.toString(px)).setScale(ins.getPipScale() + 1, RoundingMode.HALF_UP).doubleValue();
        }

        boolean live(long t) {
            for (long[] w : windows) if (t >= w[0] && t < w[1]) return true;
            return false;
        }

        public void onStart(IContext c) { ctx = c; }

        public void onTick(Instrument i, ITick tick) throws JFException {
            if (i != ins || !reason.equals("open")) return;
            long t = tick.getTime();
            if (fillMs >= 0) {
                if (t >= nextFlat) {
                    order.close();
                    reason = "flat";
                }
                return;
            }
            boolean pending = order != null && order.getState() == IOrder.State.OPENED;
            if (live(t) && !pending) {
                // shortcut: prices rounded to the nearest 0.1 pip (JForex rejects finer ones); the engine uses exact levels
                order = ctx.getEngine().submitOrder("o" + id + "x" + submits++, ins,
                        dir == 1 ? IEngine.OrderCommand.BUYLIMIT : IEngine.OrderCommand.SELLLIMIT, 0.01,
                        grid(entry), 0, grid(stop), grid(target));
            } else if (!live(t) && pending) {
                order.close();  // outside the session or past the engine's cancel time: no resting order
            }
            if (t >= windows[windows.length - 1][1] && order != null && order.getState() != IOrder.State.FILLED) {
                reason = "cancelled";
                ctx.stop();
            }
        }

        public void onMessage(IMessage m) {
            IOrder o = m.getOrder();
            if (o == null || o != order) return;
            switch (m.getType()) {
                case ORDER_FILL_OK -> {
                    fillMs = o.getFillTime();
                    fillPx = o.getOpenPrice();
                    for (long f : flats) if (f > fillMs) { nextFlat = f; break; }
                }
                case ORDER_CLOSE_OK -> {
                    if (fillMs < 0) return;  // a pending order cancelled at a session edge
                    exitMs = o.getCloseTime();
                    exitPx = o.getClosePrice();
                    if (m.getReasons().contains(IMessage.Reason.ORDER_CLOSED_BY_SL)) reason = "sl";
                    else if (m.getReasons().contains(IMessage.Reason.ORDER_CLOSED_BY_TP)) reason = "tp";
                    else if (!reason.equals("flat")) reason = "closed";
                    ctx.stop();
                }
                case ORDER_SUBMIT_REJECTED, ORDER_FILL_REJECTED -> {
                    reason = "rejected:" + m.getContent().replaceAll("[,\\s]+", "_");
                    ctx.stop();
                }
                default -> {}
            }
        }

        public void onBar(Instrument i, Period p, IBar a, IBar b) {}
        public void onAccount(IAccount a) {}
        public void onStop() {}
    }
}
