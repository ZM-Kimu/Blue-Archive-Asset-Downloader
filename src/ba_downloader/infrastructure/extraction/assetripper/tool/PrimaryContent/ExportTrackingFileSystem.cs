using System.Collections.Concurrent;
using System.Diagnostics.CodeAnalysis;
using System.Security.Cryptography;
using System.Text;
using AssetRipper.IO.Files;

namespace Baad.AssetRipper.PrimaryContent;

public sealed record ExportedFileMetadata(long Size, long MtimeNs, string Sha256);

public sealed class ExportTrackingFileSystem : FileSystem
{
	private readonly FileSystem inner;
	private readonly ConcurrentDictionary<string, ExportedFileMetadata> metadata;

	public ExportTrackingFileSystem(FileSystem inner)
	{
		this.inner = inner ?? throw new ArgumentNullException(nameof(inner));
		metadata = new ConcurrentDictionary<string, ExportedFileMetadata>(
			OperatingSystem.IsWindows() ? StringComparer.OrdinalIgnoreCase : StringComparer.Ordinal);
		File = new TrackingFileImplementation(this);
		Directory = new DelegatingDirectoryImplementation(this);
		Path = new DelegatingPathImplementation(this);
	}

	public override TrackingFileImplementation File { get; }
	public override DelegatingDirectoryImplementation Directory { get; }
	public override DelegatingPathImplementation Path { get; }

	public override string TemporaryDirectory
	{
		get => inner.TemporaryDirectory;
		set => inner.TemporaryDirectory = value;
	}

	public bool TryGetMetadata(string path, [NotNullWhen(true)] out ExportedFileMetadata? value) =>
		metadata.TryGetValue(Normalize(path), out value);

	private string Normalize(string path) => inner.Path.GetFullPath(path);

	private void RemoveMetadata(string path) => metadata.TryRemove(Normalize(path), out _);

	private void RegisterKnownHash(string path, long size, byte[] hash)
	{
		FileInfo info = new(Normalize(path));
		if (!info.Exists || info.Length != size)
		{
			throw new InvalidDataException("Tracked output file metadata is inconsistent.");
		}
		metadata[info.FullName] = new ExportedFileMetadata(
			info.Length,
			(info.LastWriteTimeUtc.Ticks - DateTime.UnixEpoch.Ticks) * 100,
			Convert.ToHexString(hash).ToLowerInvariant());
	}

	private void RegisterByReading(string path)
	{
		string normalized = Normalize(path);
		FileInfo info = new(normalized);
		using Stream stream = inner.File.OpenRead(normalized);
		RegisterKnownHash(normalized, info.Length, SHA256.HashData(stream));
	}

	public sealed class TrackingFileImplementation(ExportTrackingFileSystem owner)
		: FileImplementation(owner)
	{
		public override Stream Create(string path)
		{
			owner.RemoveMetadata(path);
			return new TrackingWriteStream(owner.inner.File.Create(path), path, owner);
		}

		public override void Delete(string path)
		{
			owner.inner.File.Delete(path);
			owner.RemoveMetadata(path);
		}

		public override bool Exists(string path) => owner.inner.File.Exists(path);
		public override Stream OpenRead(string path) => owner.inner.File.OpenRead(path);

		public override Stream OpenWrite(string path)
		{
			owner.RemoveMetadata(path);
			return new TrackingWriteStream(owner.inner.File.OpenWrite(path), path, owner);
		}

		public override byte[] ReadAllBytes(string path) => owner.inner.File.ReadAllBytes(path);
		public override string ReadAllText(string path) => owner.inner.File.ReadAllText(path);
		public override string ReadAllText(string path, Encoding encoding) =>
			owner.inner.File.ReadAllText(path, encoding);

		public override void WriteAllBytes(string path, ReadOnlySpan<byte> bytes)
		{
			owner.RemoveMetadata(path);
			owner.inner.File.WriteAllBytes(path, bytes);
			owner.RegisterKnownHash(path, bytes.Length, SHA256.HashData(bytes));
		}

		public override void WriteAllText(string path, ReadOnlySpan<char> contents)
		{
			WriteAllText(path, contents, new UTF8Encoding(false));
		}

		public override void WriteAllText(
			string path,
			ReadOnlySpan<char> contents,
			Encoding encoding)
		{
			owner.RemoveMetadata(path);
			using Stream stream = Create(path);
			using StreamWriter writer = new(stream, encoding, bufferSize: 1024, leaveOpen: false);
			writer.Write(contents);
		}
	}

	public sealed class DelegatingDirectoryImplementation(ExportTrackingFileSystem owner)
		: DirectoryImplementation(owner)
	{
		public override IEnumerable<string> EnumerateDirectories(
			string path, string searchPattern, SearchOption searchOption) =>
			owner.inner.Directory.EnumerateDirectories(path, searchPattern, searchOption);
		public override IEnumerable<string> EnumerateFiles(
			string path, string searchPattern, SearchOption searchOption) =>
			owner.inner.Directory.EnumerateFiles(path, searchPattern, searchOption);
		public override string[] GetDirectories(
			string path, string searchPattern, SearchOption searchOption) =>
			owner.inner.Directory.GetDirectories(path, searchPattern, searchOption);
		public override string[] GetFiles(
			string path, string searchPattern, SearchOption searchOption) =>
			owner.inner.Directory.GetFiles(path, searchPattern, searchOption);
		public override IEnumerable<string> EnumerateDirectories(string path, string searchPattern) =>
			owner.inner.Directory.EnumerateDirectories(path, searchPattern);
		public override IEnumerable<string> EnumerateFiles(string path, string searchPattern) =>
			owner.inner.Directory.EnumerateFiles(path, searchPattern);
		public override string[] GetDirectories(string path, string searchPattern) =>
			owner.inner.Directory.GetDirectories(path, searchPattern);
		public override string[] GetFiles(string path, string searchPattern) =>
			owner.inner.Directory.GetFiles(path, searchPattern);
		public override IEnumerable<string> EnumerateDirectories(string path) =>
			owner.inner.Directory.EnumerateDirectories(path);
		public override IEnumerable<string> EnumerateFiles(string path) =>
			owner.inner.Directory.EnumerateFiles(path);
		public override string[] GetDirectories(string path) => owner.inner.Directory.GetDirectories(path);
		public override string[] GetFiles(string path) => owner.inner.Directory.GetFiles(path);
		public override bool Exists(string path) => owner.inner.Directory.Exists(path);
		public override void Create(string path) => owner.inner.Directory.Create(path);
		public override void Delete(string path) => owner.inner.Directory.Delete(path);
	}

	public sealed class DelegatingPathImplementation(ExportTrackingFileSystem owner)
		: PathImplementation(owner)
	{
		public override string GetFullPath(string path) => owner.inner.Path.GetFullPath(path);
		public override bool IsPathRooted(ReadOnlySpan<char> path) => owner.inner.Path.IsPathRooted(path);
	}

	private sealed class TrackingWriteStream : Stream
	{
		private readonly Stream inner;
		private readonly string path;
		private readonly ExportTrackingFileSystem owner;
		private readonly IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
		private long nextPosition;
		private bool requiresReadback;
		private bool disposed;

		public TrackingWriteStream(Stream inner, string path, ExportTrackingFileSystem owner)
		{
			this.inner = inner;
			this.path = path;
			this.owner = owner;
			nextPosition = inner.CanSeek ? inner.Position : 0;
			requiresReadback = nextPosition != 0 || (inner.CanSeek && inner.Length != 0);
		}

		public override bool CanRead => inner.CanRead;
		public override bool CanSeek => inner.CanSeek;
		public override bool CanWrite => inner.CanWrite;
		public override long Length => inner.Length;
		public override long Position
		{
			get => inner.Position;
			set
			{
				if (value != nextPosition)
				{
					requiresReadback = true;
				}
				inner.Position = value;
			}
		}

		public override void Flush() => inner.Flush();
		public override Task FlushAsync(CancellationToken cancellationToken) =>
			inner.FlushAsync(cancellationToken);

		public override int Read(byte[] buffer, int offset, int count)
		{
			requiresReadback = true;
			return inner.Read(buffer, offset, count);
		}

		public override long Seek(long offset, SeekOrigin origin)
		{
			long position = inner.Seek(offset, origin);
			if (position != nextPosition)
			{
				requiresReadback = true;
			}
			return position;
		}

		public override void SetLength(long value)
		{
			requiresReadback = true;
			inner.SetLength(value);
		}

		public override void Write(byte[] buffer, int offset, int count) =>
			Write(buffer.AsSpan(offset, count));

		public override void Write(ReadOnlySpan<byte> buffer)
		{
			PrepareWrite();
			inner.Write(buffer);
			TrackWrite(buffer);
		}

		public override async ValueTask WriteAsync(
			ReadOnlyMemory<byte> buffer,
			CancellationToken cancellationToken = default)
		{
			PrepareWrite();
			await inner.WriteAsync(buffer, cancellationToken).ConfigureAwait(false);
			TrackWrite(buffer.Span);
		}

		private void PrepareWrite()
		{
			if (inner.CanSeek && inner.Position != nextPosition)
			{
				requiresReadback = true;
			}
		}

		private void TrackWrite(ReadOnlySpan<byte> buffer)
		{
			if (!requiresReadback)
			{
				hash.AppendData(buffer);
			}
			nextPosition = inner.CanSeek ? inner.Position : nextPosition + buffer.Length;
		}

		protected override void Dispose(bool disposing)
		{
			if (disposing && !disposed)
			{
				disposed = true;
				inner.Dispose();
				if (requiresReadback)
				{
					owner.RegisterByReading(path);
				}
				else
				{
					owner.RegisterKnownHash(path, nextPosition, hash.GetHashAndReset());
				}
				hash.Dispose();
			}
			base.Dispose(disposing);
		}
	}
}
