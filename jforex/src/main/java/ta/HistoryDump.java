package ta;

import com.dukascopy.api.*;
import com.dukascopy.api.system.ClientFactory;
import com.dukascopy.api.system.IClient;
import com.dukascopy.api.system.ISystemListener;

import java.io.PrintWriter;
import java.nio.file.*;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.util.*;

/**
 * Dump M1 bid/ask history through a logged-in JForex demo session.
 * Args: outDir PAIR:YYYY-MM ...   Env: DUKASCOPY_USER, DUKASCOPY_PASSWORD, optional DUKASCOPY_JNLP.
 * Writes outDir/PAIR_YYYY-MM.csv in the ta M1 schema (ts in epoch ms) and prints "DONE PAIR YYYY-MM path secs".
 * Same row rule as the datafeed decoder: keep a minute if either side has volume; a side with none borrows the other.
 */
public class HistoryDump {
    public static void main(String[] args) throws Exception {
        Path out = Paths.get(args[0]);
        Files.createDirectories(out);
        List<String[]> jobs = new ArrayList<>();
        for (int i = 1; i < args.length; i++) jobs.add(args[i].split(":"));

        IClient client = ClientFactory.getDefaultInstance();
        client.setSystemListener(new ISystemListener() {
            public void onStart(long id) {}
            public void onStop(long id) {}
            public void onConnect() {}
            public void onDisconnect() {}
        });
        String jnlp = System.getenv().getOrDefault("DUKASCOPY_JNLP", "https://platform.dukascopy.com/demo/jforex.jnlp");
        client.connect(jnlp, System.getenv("DUKASCOPY_USER"), System.getenv("DUKASCOPY_PASSWORD"));
        for (int i = 0; i < 60 && !client.isConnected(); i++) Thread.sleep(1000);
        if (!client.isConnected()) {
            System.err.println("ERROR could not connect to JForex demo (check login in .env)");
            System.exit(2);
        }
        Set<Instrument> instruments = new HashSet<>();
        for (String[] j : jobs) instruments.add(Instrument.fromString(j[0].substring(0, 3) + "/" + j[0].substring(3)));
        client.setSubscribedInstruments(instruments);

        client.startStrategy(new IStrategy() {
            public void onStart(IContext ctx) {
                int failed = 0;
                for (String[] j : jobs) {
                    try {
                        dump(ctx.getHistory(), out, j[0], YearMonth.parse(j[1]));
                    } catch (Exception e) {
                        failed++;
                        System.out.println("FAIL " + j[0] + " " + j[1] + ": " + e);
                    }
                }
                System.out.flush();
                System.exit(failed == 0 ? 0 : 1);
            }
            public void onTick(Instrument i, ITick t) {}
            public void onBar(Instrument i, Period p, IBar a, IBar b) {}
            public void onMessage(IMessage m) {}
            public void onAccount(IAccount a) {}
            public void onStop() {}
        });
        Thread.currentThread().join();  // the strategy exits the JVM when done
    }

    static void dump(IHistory h, Path out, String pair, YearMonth ym) throws Exception {
        long t0 = System.currentTimeMillis();
        Instrument ins = Instrument.fromString(pair.substring(0, 3) + "/" + pair.substring(3));
        long from = ym.atDay(1).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli();
        long to = ym.plusMonths(1).atDay(1).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli() - 60_000;
        List<IBar> bid = h.getBars(ins, Period.ONE_MIN, OfferSide.BID, Filter.NO_FILTER, from, to);
        List<IBar> ask = h.getBars(ins, Period.ONE_MIN, OfferSide.ASK, Filter.NO_FILTER, from, to);
        if (bid.size() != ask.size()) throw new IllegalStateException("bid/ask length " + bid.size() + " vs " + ask.size());
        Path tmp = out.resolve(pair + "_" + ym + ".csv.tmp"), dst = out.resolve(pair + "_" + ym + ".csv");
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(tmp))) {
            w.println("ts,bid_o,bid_h,bid_l,bid_c,ask_o,ask_h,ask_l,ask_c,volume");
            for (int i = 0; i < bid.size(); i++) {
                IBar b = bid.get(i), a = ask.get(i);
                if (b.getTime() != a.getTime()) throw new IllegalStateException("misaligned at " + b.getTime());
                boolean hb = b.getVolume() > 0, ha = a.getVolume() > 0;
                if (!hb && !ha) continue;
                IBar bb = hb ? b : a, aa = ha ? a : b;
                w.println(b.getTime() + "," + bb.getOpen() + "," + bb.getHigh() + "," + bb.getLow() + "," + bb.getClose()
                        + "," + aa.getOpen() + "," + aa.getHigh() + "," + aa.getLow() + "," + aa.getClose()
                        + "," + bb.getVolume());
            }
        }
        Files.move(tmp, dst, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        System.out.println("DONE " + pair + " " + ym + " " + dst + " " + (System.currentTimeMillis() - t0) / 1000);
        System.out.flush();
    }
}
