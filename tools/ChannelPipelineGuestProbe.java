package dev.oreslang.launcher;

import dev.oreslang.runtime.ChannelRuntime;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

/** Test-only runtime observation. All application behavior executes from .atto. */
public final class ChannelPipelineGuestProbe {
  private static void registrations(int expectedSelections, int expectedArms) {
    try {
      Field selections = ChannelRuntime.class.getDeclaredField("ACTIVE");
      Field arms = ChannelRuntime.class.getDeclaredField("activeArmRegistrations");
      selections.setAccessible(true);
      arms.setAccessible(true);
      if (((Set<?>) selections.get(null)).size() != expectedSelections || arms.getInt(null) != expectedArms) {
        throw new AssertionError("expected " + expectedSelections + "/" + expectedArms + ", actual " + ((Set<?>) selections.get(null)).size() + "/" + arms.getInt(null));
      }
    } catch (ReflectiveOperationException error) {
      throw new AssertionError(error);
    }
  }

  private static void noWaiters() { registrations(0, 0); }

  public static void main(String[] args) throws Exception {
    PrintStream report = System.out;
    for (String argument : args) {
      Path path = Path.of(argument).toAbsolutePath();
      String expected = Files.readString(path.resolveSibling(
          path.getFileName().toString().replace(".atto", ".out"))).strip();
      class Capture extends ByteArrayOutputStream {
        boolean observedBeforeReturn;
        int boundObservations;
        private void inspect() {
          String text = toString(StandardCharsets.UTF_8);
          if (text.endsWith("jobs full\n") || text.endsWith("results full\n")) {
            registrations(1, 1);
            boundObservations++;
          }
          if (toString(StandardCharsets.UTF_8).strip().equals(expected)) {
            // This executes inside the guest's last println, before teardown.
            noWaiters();
            observedBeforeReturn = true;
          }
        }
        public synchronized void write(int value) { super.write(value); inspect(); }
        public synchronized void write(byte[] data, int offset, int length) {
          super.write(data, offset, length); inspect();
        }
      }
      Capture capture = new Capture();
      int status;
      try {
        System.setOut(new PrintStream(capture, true, StandardCharsets.UTF_8));
        status = OresMain.exitStatusForArgs(new String[]{path.toString()});
      } finally {
        System.setOut(report);
      }
      String actual = capture.toString(StandardCharsets.UTF_8).strip();
      if (status != 0 || !expected.equals(actual) || !capture.observedBeforeReturn) {
        throw new AssertionError(path + ": status=" + status + ", expected " + expected + ", got " + actual);
      }
      if (path.getFileName().toString().equals("pipeline_bounds.atto") && capture.boundObservations < 2) {
        throw new AssertionError("missing live registration bound observations");
      }
      noWaiters();
      report.println("PASS " + path.getFileName() + " exact stdout; 0 retained selections/arms before/after teardown");
    }
  }
}
