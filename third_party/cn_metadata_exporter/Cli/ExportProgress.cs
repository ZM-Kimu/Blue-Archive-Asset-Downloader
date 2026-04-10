using System.Text;

namespace YldaDumpCsExporter;

internal sealed class ExportProgress
{
    private readonly bool _enabled;
    private readonly TextWriter _writer;
    private readonly bool _interactive;
    private readonly object _sync = new();
    private readonly Dictionary<string, LoopState> _loopStates = new(StringComparer.Ordinal);
    private DateTime _lastLoopWriteUtc = DateTime.MinValue;
    private int _lastLoopPercent = -1;
    private bool _loopLineActive;

    public ExportProgress(bool enabled = true, TextWriter? writer = null)
    {
        _enabled = enabled;
        _writer = writer ?? Console.Error;
        _interactive = !Console.IsErrorRedirected;
    }

    public void Stage(string name, int current, int total)
    {
        if (!_enabled)
            return;

        lock (_sync)
        {
            FlushLoopLine_NoLock();
            _writer.WriteLine($"{RenderBar(current, total, 24)} [{current}/{total}] {name}");
        }
    }

    public void Loop(string name, int current, int total)
    {
        if (!_enabled || total <= 0)
            return;

        var percent = Math.Clamp((int)Math.Floor((current * 100.0) / total), 0, 100);
        var now = DateTime.UtcNow;
        if (current < total &&
            percent == _lastLoopPercent &&
            (now - _lastLoopWriteUtc).TotalMilliseconds < 200)
        {
            return;
        }

        lock (_sync)
        {
            if (current < total &&
                percent == _lastLoopPercent &&
                (now - _lastLoopWriteUtc).TotalMilliseconds < 200)
            {
                return;
            }

            if (!_loopStates.TryGetValue(name, out var state))
            {
                state = new LoopState(now);
                _loopStates[name] = state;
            }

            var elapsedSeconds = Math.Max((now - state.StartUtc).TotalSeconds, 0.001);
            var rate = current / elapsedSeconds;
            var rateText = rate >= 10 ? $"{rate,6:F0}/s" : $"{rate,6:F1}/s";
            var line = $"    {name} {RenderBar(current, total, 18)} {percent,3}% ({current}/{total}, {rateText})";
            if (_interactive)
            {
                var padded = line.PadRight(Console.BufferWidth > 0 ? Math.Max(0, Console.BufferWidth - 1) : line.Length);
                _writer.Write('\r');
                _writer.Write(padded);
            }
            else
            {
                _writer.WriteLine(line);
            }

            _loopLineActive = _interactive && current < total;
            _lastLoopPercent = percent;
            _lastLoopWriteUtc = now;

            if (current >= total)
                FlushLoopLine_NoLock();
        }
    }

    public void Complete()
    {
        if (!_enabled)
            return;

        lock (_sync)
            FlushLoopLine_NoLock();
    }

    private void FlushLoopLine_NoLock()
    {
        if (!_loopLineActive)
            return;

        _writer.WriteLine();
        _loopLineActive = false;
    }

    private static string RenderBar(int current, int total, int width)
    {
        if (total <= 0)
            return "[" + new string('.', width) + "]";

        var filled = Math.Clamp((int)Math.Round(current * width / (double)total), 0, width);
        var builder = new StringBuilder(width + 2);
        builder.Append('[');
        builder.Append('#', filled);
        builder.Append('.', width - filled);
        builder.Append(']');
        return builder.ToString();
    }

    private sealed record LoopState(DateTime StartUtc);
}
