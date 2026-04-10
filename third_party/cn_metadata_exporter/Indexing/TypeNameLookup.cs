namespace YldaDumpCsExporter;

internal sealed class TypeNameLookup : IReadOnlyDictionary<uint, string>
{
    private readonly IReadOnlyDictionary<uint, string> _globalMap;
    private readonly IReadOnlyDictionary<uint, string> _localOverrides;
    private int? _count;

    public TypeNameLookup(
        IReadOnlyDictionary<uint, string> globalMap,
        IReadOnlyDictionary<uint, string> localOverrides)
    {
        _globalMap = globalMap;
        _localOverrides = localOverrides;
    }

    public string this[uint key]
        => _localOverrides.TryGetValue(key, out var localValue) ? localValue : _globalMap[key];

    public IEnumerable<uint> Keys
    {
        get
        {
            var seen = new HashSet<uint>();
            foreach (var key in _localOverrides.Keys)
            {
                if (seen.Add(key))
                    yield return key;
            }

            foreach (var key in _globalMap.Keys)
            {
                if (seen.Add(key))
                    yield return key;
            }
        }
    }

    public IEnumerable<string> Values => this.Select(pair => pair.Value);

    public int Count
    {
        get
        {
            if (_count.HasValue)
                return _count.Value;

            if (_localOverrides.Count == 0)
            {
                _count = _globalMap.Count;
                return _count.Value;
            }

            var seen = new HashSet<uint>(_globalMap.Keys);
            seen.UnionWith(_localOverrides.Keys);
            _count = seen.Count;
            return _count.Value;
        }
    }

    public bool ContainsKey(uint key)
        => _localOverrides.ContainsKey(key) || _globalMap.ContainsKey(key);

    public bool TryGetValue(uint key, out string value)
    {
        if (_localOverrides.TryGetValue(key, out value!))
            return true;

        return _globalMap.TryGetValue(key, out value!);
    }

    public IEnumerator<KeyValuePair<uint, string>> GetEnumerator()
    {
        var seen = new HashSet<uint>();
        foreach (var pair in _localOverrides)
        {
            if (seen.Add(pair.Key))
                yield return pair;
        }

        foreach (var pair in _globalMap)
        {
            if (seen.Add(pair.Key))
                yield return pair;
        }
    }

    System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator()
        => GetEnumerator();
}
