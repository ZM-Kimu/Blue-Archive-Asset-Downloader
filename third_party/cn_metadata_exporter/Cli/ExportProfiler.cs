using System.Diagnostics;

namespace YldaDumpCsExporter;

internal sealed class ExportProfiler
{
    private readonly bool _enabled;
    private readonly Dictionary<string, long> _durationsMs = new(StringComparer.Ordinal);

    public ExportProfiler(bool enabled)
    {
        _enabled = enabled;
    }

    public T Measure<T>(string stage, Func<T> action)
    {
        if (!_enabled)
            return action();

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return action();
        }
        finally
        {
            stopwatch.Stop();
            Record(stage, stopwatch.ElapsedMilliseconds);
        }
    }

    public void Measure(string stage, Action action)
    {
        if (!_enabled)
        {
            action();
            return;
        }

        var stopwatch = Stopwatch.StartNew();
        try
        {
            action();
        }
        finally
        {
            stopwatch.Stop();
            Record(stage, stopwatch.ElapsedMilliseconds);
        }
    }

    public IReadOnlyDictionary<string, long> Snapshot()
        => new Dictionary<string, long>(_durationsMs, StringComparer.Ordinal);

    public void Print(TextWriter writer, string cacheStatus)
    {
        if (!_enabled)
            return;

        writer.WriteLine("Timing summary:");
        foreach (var pair in _durationsMs.OrderBy(pair => pair.Key, StringComparer.Ordinal))
            writer.WriteLine($"  {pair.Key}: {pair.Value} ms");
        writer.WriteLine($"  cache: {cacheStatus}");
    }

    private void Record(string stage, long elapsedMs)
    {
        if (_durationsMs.TryGetValue(stage, out var current))
            _durationsMs[stage] = current + elapsedMs;
        else
            _durationsMs[stage] = elapsedMs;
    }
}
