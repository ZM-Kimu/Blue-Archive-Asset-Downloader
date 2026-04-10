using System.Security.Cryptography;
using System.Text;

namespace YldaDumpCsExporter;

internal static class YldaMetadataRestorer
{
    public const uint DefaultKeyConstant = 0xD96603C0;

    private static readonly byte[] ProtectedMagic = [0x94, 0x43, 0x72, 0x12];
    private static readonly byte[] RestoreIv = Enumerable.Range(2, 16).Select(value => (byte)value).ToArray();

    public static bool LooksProtected(ReadOnlySpan<byte> buffer)
        => buffer.Length >= ProtectedMagic.Length && buffer[..ProtectedMagic.Length].SequenceEqual(ProtectedMagic);

    public static byte[] Restore(byte[] raw, uint keyConstant = DefaultKeyConstant)
    {
        var restored = (byte[])raw.Clone();
        var xorByte = DeriveXorByte(keyConstant);
        var aesKey = DeriveAsciiKeyMaterial(keyConstant);

        for (var i = 8; i < Math.Min(0x1000, restored.Length); i++)
            restored[i] ^= xorByte;

        for (var offset = 0x1000; offset < Math.Min(0x5000, restored.Length); offset += 0x800)
        {
            if (offset + 0x800 > restored.Length)
                break;

            DecryptChunkInPlace(restored, offset, 0x800, aesKey, RestoreIv);
        }

        var tailLength = restored.Length - 0x11000;
        if (tailLength > 0)
        {
            var blockCount = 0;
            if (tailLength >= 0x10000)
            {
                blockCount = ((restored.Length - 0x21000) >> 16) + 1;
                for (var blockIndex = 0; blockIndex < blockCount; blockIndex++)
                {
                    var start = 0x11000 + blockIndex * 0x10000;
                    var end = Math.Min(restored.Length, start + 0x4000);
                    for (var i = start; i < end; i++)
                        restored[i] ^= xorByte;
                }
            }

            var remaining = tailLength - (blockCount << 16);
            if (remaining > 0)
            {
                var start = 0x11000 + (blockCount << 16);
                var end = Math.Min(restored.Length, start + remaining);
                for (var i = start; i < end; i++)
                    restored[i] ^= xorByte;
            }
        }

        return restored;
    }

    public static byte DeriveXorByte(uint keyConstant)
    {
        var key = (byte)((keyConstant >> 16) & 0xFF);
        return key == 0 ? (byte)0x87 : key;
    }

    public static byte[] DeriveAsciiKeyMaterial(uint keyConstant)
        => Encoding.ASCII.GetBytes($"{keyConstant:x8}{keyConstant:x8}");

    private static void DecryptChunkInPlace(byte[] buffer, int offset, int length, byte[] key, byte[] iv)
    {
        using var aes = Aes.Create();
        aes.Mode = CipherMode.CBC;
        aes.Padding = PaddingMode.None;
        aes.Key = key;
        aes.IV = iv;

        using var decryptor = aes.CreateDecryptor();
        var decrypted = decryptor.TransformFinalBlock(buffer, offset, length);
        Buffer.BlockCopy(decrypted, 0, buffer, offset, length);
    }
}
