namespace BAAD.MediaArchiveExtractor;

internal static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine(
                "Usage: MediaArchiveExtractor <request.json> <result.json>");
            return 2;
        }

        try
        {
            ExtractionRequest request = await MediaArchiveProtocol.ReadRequestAsync(
                args[0]);
            ExtractionResult result = await MediaArchiveEngine.ExecuteAsync(
                request,
                MediaArchiveProtocol.EmitProgress);
            await MediaArchiveProtocol.WriteResultAtomicAsync(args[1], result);
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"Media archive extractor failed: {exception.GetType().Name}: " +
                exception.Message);
            return 1;
        }
    }
}
