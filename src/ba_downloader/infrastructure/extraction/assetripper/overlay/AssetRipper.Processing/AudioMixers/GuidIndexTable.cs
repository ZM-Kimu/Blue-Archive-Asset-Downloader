using AssetRipper.Import.Logging;
using System.Globalization;

namespace AssetRipper.Processing.AudioMixers;

internal readonly struct GuidIndexTable
{
	private readonly string identity;
	private readonly Dictionary<uint, UnityGuid> table = new();

	public GuidIndexTable(string identity)
	{
		ArgumentException.ThrowIfNullOrEmpty(identity);
		this.identity = identity;
	}

	public UnityGuid this[uint index] => table[index];

	public bool ContainsKey(uint index) => table.ContainsKey(index);

	public bool TryGetValue(uint index, out UnityGuid guid) => table.TryGetValue(index, out guid);

	public UnityGuid IndexNewGuid(uint index)
	{
		if (table.TryGetValue(index, out UnityGuid guid))
		{
			Logger.Warning(LogCategory.Processing, $"Constant index #{index} conflicts with another one.");
		}
		else
		{
			guid = UnityGuid.Md5Hash(
				string.Concat(
					identity,
					":parameter:",
					index.ToString(CultureInfo.InvariantCulture)));
			table.Add(index, guid);
		}
		return guid;
	}
}
