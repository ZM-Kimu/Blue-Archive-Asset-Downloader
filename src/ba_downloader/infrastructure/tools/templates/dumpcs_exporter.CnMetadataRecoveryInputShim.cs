using System.Text;
using System.Reflection;
using LibCpp2IL;
using LibCpp2IL.BinaryStructures;
using LibCpp2IL.Metadata;

internal static class CnMetadataRecoveryInputShim
{
    private const int PointerSize = 8;
    private const int CodeGenModuleSizeV27_2 = 18 * PointerSize;
    private const uint ParameterAttributesHasDefault = 0x1000;
    private const ulong CnRecoveryRealCodeRegistrationVa = 0xAD5DEC8;
    private const uint CnRecoveryGenericXorMask = 0xCDCDCDCD;
    private const int CnRecoveryGenericInstEncodedOffset = 0x28600;
    private static bool IsRegistered;
    private static readonly int[] AggressiveGenericInstOffsets =
    [
        0x28600,
        0x18000,
        0x19800,
        0x1E000,
        0x1E800,
        0x20000,
        0x21000,
        0x28800,
        0x2A800,
        0x2D000,
        0x2E000,
        0x2F800,
        0x31000,
    ];
    private static readonly byte[] Marker = Encoding.ASCII.GetBytes("CN_METADATA_RECOVERY_SYNTH_CGM\0");
    public static void Register()
    {
        if (IsRegistered)
            return;

        Il2CppBinary.OnRegistrationStructLocationFailure += OnRegistrationFallback;
        IsRegistered = true;
    }

    private static void OnRegistrationFallback(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        ref Il2CppCodeRegistration? codeReg,
        ref Il2CppMetadataRegistration? metadataReg)
    {
        if (codeReg != null)
            return;

        if (metadata.MetadataVersion < 27f || binary.PointerSize != PointerSize)
        {
            Console.Error.WriteLine("CN metadata recovery shim supports only 64-bit metadata v27+ inputs.");
            return;
        }

        ClearCustomAttributeRanges(metadata);
        ClearParameterDefaultAttributeBits(binary, metadata, metadataReg);

        var raw = GetMutableRawBinaryContent(binary);
        if (TryUseRealCodeRegistration(binary, metadata, raw, metadataReg, ref codeReg))
            return;

        var imageNames = metadata.imageDefinitions
            .Select((image, index) => (name: image.Name ?? $"module_{index}.dll", index))
            .ToArray();

        var bytesNeeded = EstimateSyntheticBlockSize(imageNames.Select(x => x.name));
        var rawOffset = FindZeroRun(raw, bytesNeeded, 8);
        if (rawOffset < 0 || !TryMapRawToVirtual(binary, rawOffset, out var baseVa))
        {
            Console.Error.WriteLine($"Unable to find a mapped zero run for synthetic codegen modules. Need 0x{bytesNeeded:X} bytes.");
            return;
        }

        var cursor = Align(rawOffset + Marker.Length, PointerSize);
        Array.Copy(Marker, 0, raw, rawOffset, Marker.Length);

        var ptrListOff = cursor;
        var ptrListVa = baseVa + (ulong)(ptrListOff - rawOffset);
        cursor += imageNames.Length * PointerSize;

        var zeroMethodArrayOff = cursor;
        var zeroMethodArrayVa = baseVa + (ulong)(zeroMethodArrayOff - rawOffset);
        WriteU64(raw, zeroMethodArrayOff, 0);
        cursor += PointerSize;

        var moduleStructOff = Align(cursor, PointerSize);
        cursor = moduleStructOff + imageNames.Length * CodeGenModuleSizeV27_2;

        foreach (var (name, index) in imageNames)
        {
            var nameBytes = Encoding.ASCII.GetBytes(name);
            var nameOff = cursor;
            var nameVa = baseVa + (ulong)(nameOff - rawOffset);
            Array.Copy(nameBytes, 0, raw, nameOff, nameBytes.Length);
            raw[nameOff + nameBytes.Length] = 0;
            cursor += nameBytes.Length + 1;
            cursor = Align(cursor, PointerSize);

            var moduleOff = moduleStructOff + index * CodeGenModuleSizeV27_2;
            var moduleVa = baseVa + (ulong)(moduleOff - rawOffset);
            WriteU64(raw, ptrListOff + index * PointerSize, moduleVa);

            WriteU64(raw, moduleOff + 0 * PointerSize, nameVa);
            WriteU64(raw, moduleOff + 1 * PointerSize, 1);
            WriteU64(raw, moduleOff + 2 * PointerSize, zeroMethodArrayVa);
            for (var field = 3; field < 18; field++)
                WriteU64(raw, moduleOff + field * PointerSize, 0);
        }

        Console.WriteLine($"CN metadata recovery shim wrote {imageNames.Length} synthetic codegen modules at VA 0x{ptrListVa:X}.");
        codeReg = new Il2CppCodeRegistration
        {
            codeGenModulesCount = (uint)imageNames.Length,
            addrCodeGenModulePtrs = ptrListVa,
        };
    }

    private static bool TryUseRealCodeRegistration(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        byte[] raw,
        Il2CppMetadataRegistration? metadataReg,
        ref Il2CppCodeRegistration? codeReg)
    {
        foreach (var registrationCandidate in EnumerateCodeRegistrationCandidates(binary, metadata, raw))
        {
            try
            {
                if (TryUseCodeRegistrationCandidate(binary, metadata, raw, metadataReg, registrationCandidate, ref codeReg))
                    return true;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"CN metadata recovery shim rejected {registrationCandidate.Source} CodeRegistration at 0x{registrationCandidate.Va:X}: {ex.Message}");
            }
        }

        return false;
    }

    private static IEnumerable<CodeRegistrationCandidate> EnumerateCodeRegistrationCandidates(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        byte[] raw)
    {
        var seen = new HashSet<ulong>();

        if (TryFindCodeRegistrationCandidate(binary, raw, metadata.imageDefinitions.Length, out var scannedVa, out var moduleArrayVa, out var score) &&
            seen.Add(scannedVa))
        {
            yield return new CodeRegistrationCandidate(scannedVa, $"auto-scanned(score={score}, modules=0x{moduleArrayVa:X})");
        }

        if (seen.Add(CnRecoveryRealCodeRegistrationVa))
            yield return new CodeRegistrationCandidate(CnRecoveryRealCodeRegistrationVa, "CN-metadata-recovery-known");
    }

    private static bool TryFindCodeRegistrationCandidate(
        Il2CppBinary binary,
        byte[] raw,
        int moduleCount,
        out ulong codeRegistrationVa,
        out ulong moduleArrayVa,
        out int bestScore)
    {
        codeRegistrationVa = 0;
        moduleArrayVa = 0;
        bestScore = 0;

        var targetCount = (ulong)moduleCount;
        for (var offset = 13 * PointerSize; offset + 2 * PointerSize <= raw.Length; offset += PointerSize)
        {
            if (ReadU64(raw, offset) != targetCount)
                continue;

            var candidateModuleArrayVa = ReadU64(raw, offset + PointerSize);
            if (!ScoreModulePointerArray(binary, candidateModuleArrayVa, moduleCount, out var moduleScore))
                continue;

            var startOffset = offset - 13 * PointerSize;
            if (!TryMapRawToVirtual(binary, startOffset, out var candidateCodeRegistrationVa))
                continue;

            var registrationScore = moduleScore * 10 + ScoreRegistrationPrefix(binary, raw, startOffset);
            if (registrationScore <= bestScore)
                continue;

            bestScore = registrationScore;
            codeRegistrationVa = candidateCodeRegistrationVa;
            moduleArrayVa = candidateModuleArrayVa;
        }

        return codeRegistrationVa != 0;
    }

    private static bool ScoreModulePointerArray(
        Il2CppBinary binary,
        ulong moduleArrayVa,
        int moduleCount,
        out int score)
    {
        score = 0;
        if (moduleArrayVa == 0)
            return false;

        try
        {
            var modulePtrs = binary.ReadNUintArrayAtVirtualAddress(moduleArrayVa, moduleCount);
            foreach (var modulePtr in modulePtrs)
            {
                if (modulePtr == 0)
                    continue;

                var module = binary.ReadReadableAtVirtualAddress<Il2CppCodeGenModule>(modulePtr);
                if (module.methodPointerCount > 300_000)
                    continue;

                if (module.methodPointerCount == 0 ||
                    (module.methodPointers != 0 && binary.TryMapVirtualAddressToRaw(module.methodPointers, out _)))
                {
                    score++;
                }
            }
        }
        catch
        {
            score = 0;
            return false;
        }

        return score > 0;
    }

    private static int ScoreRegistrationPrefix(Il2CppBinary binary, byte[] raw, int startOffset)
    {
        if (!IsRangeInRaw(raw, startOffset, 13 * PointerSize))
            return 0;

        var values = new ulong[13];
        for (var i = 0; i < values.Length; i++)
            values[i] = ReadU64(raw, startOffset + i * PointerSize);

        var score = 0;
        if (CountedPointerLooksValid(binary, values[0], values[1], 10_000))
            score++;
        if (CountedPointerLooksValid(binary, values[2], values[3], 1_000_000))
            score++;
        if (values[2] == 0 || values[4] == 0 || binary.TryMapVirtualAddressToRaw(values[4], out _))
            score++;
        if (CountedPointerLooksValid(binary, values[5], values[6], 1_000_000))
            score++;
        if (CountedPointerLooksValid(binary, values[7], values[8], 1_000_000))
            score++;
        if (CountedPointerLooksValid(binary, values[9], values[10], 1_000_000))
            score++;
        if (CountedPointerLooksValid(binary, values[11], values[12], 10_000))
            score++;

        return score;
    }

    private static bool CountedPointerLooksValid(
        Il2CppBinary binary,
        ulong count,
        ulong pointer,
        ulong maxCount)
    {
        if (count == 0)
            return pointer == 0 || binary.TryMapVirtualAddressToRaw(pointer, out _);
        return count <= maxCount && pointer != 0 && binary.TryMapVirtualAddressToRaw(pointer, out _);
    }

    private static bool TryUseCodeRegistrationCandidate(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        byte[] raw,
        Il2CppMetadataRegistration? metadataReg,
        CodeRegistrationCandidate registrationCandidate,
        ref Il2CppCodeRegistration? codeReg)
    {
        var candidate = binary.ReadReadableAtVirtualAddress<Il2CppCodeRegistration>(registrationCandidate.Va);
        if (candidate.codeGenModulesCount != (ulong)metadata.imageDefinitions.Length ||
            candidate.addrCodeGenModulePtrs == 0)
        {
            return false;
        }

        var realModulePtrs = binary.ReadNUintArrayAtVirtualAddress(
            candidate.addrCodeGenModulePtrs,
            (long)candidate.codeGenModulesCount);
        var imageNames = metadata.imageDefinitions
            .Select((image, index) => (name: image.Name ?? $"module_{index}.dll", index))
            .ToArray();

        var bytesNeeded = EstimateSyntheticBlockSize(imageNames.Select(x => x.name));
        var rawOffset = FindZeroRun(raw, bytesNeeded, 8);
        if (rawOffset < 0 || !TryMapRawToVirtual(binary, rawOffset, out var baseVa))
            return false;

        var cursor = Align(rawOffset + Marker.Length, PointerSize);
        Array.Copy(Marker, 0, raw, rawOffset, Marker.Length);

        var ptrListOff = cursor;
        var ptrListVa = baseVa + (ulong)(ptrListOff - rawOffset);
        cursor += imageNames.Length * PointerSize;

        var moduleStructOff = Align(cursor, PointerSize);
        cursor = moduleStructOff + imageNames.Length * CodeGenModuleSizeV27_2;

        foreach (var (name, index) in imageNames)
        {
            var realModule = binary.ReadReadableAtVirtualAddress<Il2CppCodeGenModule>(realModulePtrs[index]);
            var nameBytes = Encoding.ASCII.GetBytes(name);
            var nameOff = cursor;
            var nameVa = baseVa + (ulong)(nameOff - rawOffset);
            Array.Copy(nameBytes, 0, raw, nameOff, nameBytes.Length);
            raw[nameOff + nameBytes.Length] = 0;
            cursor += nameBytes.Length + 1;
            cursor = Align(cursor, PointerSize);

            var moduleOff = moduleStructOff + index * CodeGenModuleSizeV27_2;
            var moduleVa = baseVa + (ulong)(moduleOff - rawOffset);
            WriteU64(raw, ptrListOff + index * PointerSize, moduleVa);

            WriteU64(raw, moduleOff + 0 * PointerSize, nameVa);
            WriteU64(raw, moduleOff + 1 * PointerSize, (ulong)realModule.methodPointerCount);
            WriteU64(raw, moduleOff + 2 * PointerSize, realModule.methodPointers);
            WriteU64(raw, moduleOff + 3 * PointerSize, 0);
            WriteU64(raw, moduleOff + 4 * PointerSize, 0);
            WriteU64(raw, moduleOff + 5 * PointerSize, realModule.invokerIndices);
            WriteU64(raw, moduleOff + 6 * PointerSize, realModule.reversePInvokeWrapperCount);
            WriteU64(raw, moduleOff + 7 * PointerSize, realModule.reversePInvokeWrapperIndices);
            for (var field = 8; field < 18; field++)
                WriteU64(raw, moduleOff + field * PointerSize, 0);
        }

        if (metadataReg == null ||
            IsEnvEnabled("CN_METADATA_RECOVERY_SHIM_DISABLE_GENERICS") ||
            !TryCompactGenericMethodTable(binary, metadata, metadataReg, candidate.genericMethodPointersCount, raw))
        {
            // Keep the direct Cpp2IL path stable if the protected generic side
            // tables cannot be sanitized for this sample.
            candidate.genericMethodPointersCount = 0;
            candidate.genericMethodPointers = 0;
            candidate.genericAdjustorThunks = 0;
        }
        candidate.addrCodeGenModulePtrs = ptrListVa;

        codeReg = candidate;
        Console.WriteLine($"CN metadata recovery shim using {registrationCandidate.Source} CodeRegistration at 0x{registrationCandidate.Va:X}; normalized module array 0x{ptrListVa:X}.");
        return true;
    }

    private static bool TryCompactGenericMethodTable(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        Il2CppMetadataRegistration metadataReg,
        ulong genericMethodPointerCount,
        byte[] raw)
    {
        if (metadataReg.genericMethodTableCount <= 0 ||
            metadataReg.genericMethodTable == 0 ||
            metadataReg.methodSpecsCount <= 0 ||
            metadataReg.methodSpecs == 0 ||
            metadataReg.genericInstsCount <= 0 ||
            genericMethodPointerCount == 0)
        {
            return false;
        }

        if (!binary.TryMapVirtualAddressToRaw(metadataReg.genericMethodTable, out var genericTableRaw) ||
            !binary.TryMapVirtualAddressToRaw(metadataReg.methodSpecs, out var methodSpecsRaw) ||
            !binary.TryMapVirtualAddressToRaw(metadataReg.genericInsts, out var genericInstsRaw))
        {
            return false;
        }

        var methodDefCount = metadata.MethodDefinitionCount;
        var genericInstCount = metadataReg.genericInstsCount;
        var readCount = metadataReg.genericMethodTableCount;
        var kept = 0;
        var dropped = 0;
        var rawRaw = 0;
        var tableXorRaw = 0;
        var rawMethodSpecXor = 0;
        var tableXorMethodSpecXor = 0;
        var rawMethodSpecFieldXor = 0;
        var tableXorMethodSpecFieldXor = 0;
        var genericInstOffsetFixed = 0;
        var methodSpecPermuted = 0;

        for (var readIndex = 0; readIndex < readCount; readIndex++)
        {
            var sourceOffset = genericTableRaw + readIndex * 16;
            if (!IsRangeInRaw(raw, sourceOffset, 16))
            {
                dropped++;
                continue;
            }

            if (!TryBuildAritySafeGenericMethodRowCandidate(
                    binary,
                    metadata,
                    raw,
                    genericInstsRaw,
                    sourceOffset,
                    methodSpecsRaw,
                    metadataReg.methodSpecsCount,
                    genericInstCount,
                    methodDefCount,
                    genericMethodPointerCount,
                    out var candidate))
            {
                dropped++;
                continue;
            }

            if (candidate.MethodSpecDecodeMask != 0 ||
                candidate.MethodDefinitionField != 0 ||
                candidate.ClassIndexField != 1 ||
                candidate.MethodIndexField != 2)
            {
                var methodSpecOffset = methodSpecsRaw + candidate.GenericMethodIndex * 12L;
                WriteI32(raw, methodSpecOffset, candidate.MethodDefinitionIndex);
                WriteI32(raw, methodSpecOffset + 4, candidate.ClassIndexIndex);
                WriteI32(raw, methodSpecOffset + 8, candidate.MethodIndexIndex);
            }

            var targetOffset = genericTableRaw + kept * 16;
            WriteI32(raw, targetOffset, candidate.GenericMethodIndex);
            WriteI32(raw, targetOffset + 4, candidate.MethodPointerIndex);
            WriteI32(raw, targetOffset + 8, candidate.InvokerIndex);
            WriteI32(raw, targetOffset + 12, candidate.AdjustorThunk);

            switch (candidate.Strategy)
            {
                case GenericDecodeStrategy.RawRaw:
                    rawRaw++;
                    break;
                case GenericDecodeStrategy.TableXorRaw:
                    tableXorRaw++;
                    break;
                case GenericDecodeStrategy.RawMethodSpecXor:
                    rawMethodSpecXor++;
                    break;
                case GenericDecodeStrategy.TableXorMethodSpecXor:
                    tableXorMethodSpecXor++;
                    break;
                case GenericDecodeStrategy.RawMethodSpecFieldXor:
                    rawMethodSpecFieldXor++;
                    break;
                case GenericDecodeStrategy.TableXorMethodSpecFieldXor:
                    tableXorMethodSpecFieldXor++;
                    break;
            }

            if (candidate.GenericInstOffsetFixMask != 0)
                genericInstOffsetFixed++;
            if (candidate.MethodDefinitionField != 0 ||
                candidate.ClassIndexField != 1 ||
                candidate.MethodIndexField != 2)
            {
                methodSpecPermuted++;
            }

            kept++;
        }

        metadataReg.genericMethodTableCount = kept;
        Console.WriteLine(
            "CN metadata recovery shim sanitized generic method table: " +
            $"kept {kept}, dropped {dropped}, " +
            $"raw/raw {rawRaw}, table-xor/raw {tableXorRaw}, " +
            $"raw/methodspec-xor {rawMethodSpecXor}, table-xor/methodspec-xor {tableXorMethodSpecXor}.");
        if (rawMethodSpecFieldXor > 0 || tableXorMethodSpecFieldXor > 0)
        {
            Console.WriteLine(
                "CN metadata recovery shim fieldwise generic methodSpec XOR recovery: " +
                $"raw/table {rawMethodSpecFieldXor}, table-xor {tableXorMethodSpecFieldXor}.");
        }
        if (genericInstOffsetFixed > 0)
            Console.WriteLine($"CN metadata recovery shim GenericInst encoded-offset normalization: {genericInstOffsetFixed} methodSpec rows.");
        if (methodSpecPermuted > 0)
            Console.WriteLine($"CN metadata recovery shim MethodSpec field permutation recovery: {methodSpecPermuted} methodSpec rows.");

        return kept > 0;
    }

    private static bool TryBuildGenericMethodRowCandidate(
        byte[] raw,
        long rowOffset,
        long methodSpecsRaw,
        long methodSpecsCount,
        long genericInstCount,
        int methodDefCount,
        ulong genericMethodPointerCount,
        out GenericMethodRowCandidate candidate)
    {
        if (TryBuildGenericMethodRowCandidateWithOffsets(
                raw,
                rowOffset,
                methodSpecsRaw,
                methodSpecsCount,
                genericInstCount,
                methodDefCount,
                genericMethodPointerCount,
                [CnRecoveryGenericInstEncodedOffset],
                allowAmbiguous: true,
                allowPermutations: false,
                out candidate))
        {
            return true;
        }

        if (!IsEnvEnabled("CN_METADATA_RECOVERY_SHIM_AGGRESSIVE_GENERICS"))
            return false;

        return TryBuildGenericMethodRowCandidateWithOffsets(
            raw,
            rowOffset,
            methodSpecsRaw,
            methodSpecsCount,
            genericInstCount,
            methodDefCount,
            genericMethodPointerCount,
            AggressiveGenericInstOffsets,
            allowAmbiguous: true,
            allowPermutations: true,
            out candidate);
    }

    private static bool TryBuildAritySafeGenericMethodRowCandidate(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        byte[] raw,
        long genericInstsRaw,
        long rowOffset,
        long methodSpecsRaw,
        long methodSpecsCount,
        long genericInstCount,
        int methodDefCount,
        ulong genericMethodPointerCount,
        out GenericMethodRowCandidate candidate)
    {
        foreach (var current in EnumerateGenericMethodRowCandidatesWithOffsets(
                     raw,
                     rowOffset,
                     methodSpecsRaw,
                     methodSpecsCount,
                     genericInstCount,
                     methodDefCount,
                     genericMethodPointerCount,
                     [CnRecoveryGenericInstEncodedOffset],
                     allowPermutations: false))
        {
            if (IsGenericMethodSemanticCandidate(binary, metadata, raw, genericInstsRaw, genericInstCount, current))
            {
                candidate = current;
                return true;
            }
        }

        if (IsEnvEnabled("CN_METADATA_RECOVERY_SHIM_AGGRESSIVE_GENERICS"))
        {
            foreach (var current in EnumerateGenericMethodRowCandidatesWithOffsets(
                         raw,
                         rowOffset,
                         methodSpecsRaw,
                         methodSpecsCount,
                         genericInstCount,
                         methodDefCount,
                         genericMethodPointerCount,
                         AggressiveGenericInstOffsets,
                         allowPermutations: true))
            {
                if (IsGenericMethodSemanticCandidate(binary, metadata, raw, genericInstsRaw, genericInstCount, current))
                {
                    candidate = current;
                    return true;
                }
            }
        }

        candidate = default!;
        return false;
    }

    private static bool TryBuildGenericMethodRowCandidateWithOffsets(
        byte[] raw,
        long rowOffset,
        long methodSpecsRaw,
        long methodSpecsCount,
        long genericInstCount,
        int methodDefCount,
        ulong genericMethodPointerCount,
        int[] genericInstOffsets,
        bool allowAmbiguous,
        bool allowPermutations,
        out GenericMethodRowCandidate candidate)
    {
        var candidates = EnumerateGenericMethodRowCandidatesWithOffsets(
                raw,
                rowOffset,
                methodSpecsRaw,
                methodSpecsCount,
                genericInstCount,
                methodDefCount,
                genericMethodPointerCount,
                genericInstOffsets,
                allowPermutations)
            .ToArray();

        if (allowAmbiguous && candidates.Length > 0)
        {
            candidate = candidates[0];
            return true;
        }

        var recoveryKeys = new HashSet<string>();
        foreach (var current in candidates)
            recoveryKeys.Add(current.RecoveryKey);

        if (candidates.Length > 0 && recoveryKeys.Count == 1)
        {
            candidate = candidates[0];
            return true;
        }

        candidate = default!;
        return false;
    }

    private static IEnumerable<GenericMethodRowCandidate> EnumerateGenericMethodRowCandidatesWithOffsets(
        byte[] raw,
        long rowOffset,
        long methodSpecsRaw,
        long methodSpecsCount,
        long genericInstCount,
        int methodDefCount,
        ulong genericMethodPointerCount,
        int[] genericInstOffsets,
        bool allowPermutations)
    {
        foreach (var strategy in new[]
                 {
                     GenericDecodeStrategy.RawRaw,
                     GenericDecodeStrategy.TableXorRaw,
                     GenericDecodeStrategy.RawMethodSpecXor,
                     GenericDecodeStrategy.TableXorMethodSpecXor,
                     GenericDecodeStrategy.RawMethodSpecFieldXor,
                     GenericDecodeStrategy.TableXorMethodSpecFieldXor,
                 })
        {
            var decodeTable = strategy is GenericDecodeStrategy.TableXorRaw
                or GenericDecodeStrategy.TableXorMethodSpecXor
                or GenericDecodeStrategy.TableXorMethodSpecFieldXor;

            var genericMethodIndex = ReadI32MaybeXor(raw, rowOffset, decodeTable);
            var methodPointerIndex = ReadI32MaybeXor(raw, rowOffset + 4, decodeTable);
            var invokerIndex = ReadI32MaybeXor(raw, rowOffset + 8, decodeTable);
            var adjustorThunk = ReadI32MaybeXor(raw, rowOffset + 12, decodeTable);

            if (genericMethodIndex < 0 ||
                genericMethodIndex >= methodSpecsCount ||
                methodPointerIndex < 0 ||
                (ulong)methodPointerIndex >= genericMethodPointerCount)
            {
                continue;
            }

            var methodSpecOffset = methodSpecsRaw + genericMethodIndex * 12L;
            if (!IsRangeInRaw(raw, methodSpecOffset, 12))
                continue;

            foreach (var methodSpecDecodeMask in MethodSpecDecodeMasks(strategy))
            {
                var methodDefinitionIndex = ReadI32MaybeXor(raw, methodSpecOffset, (methodSpecDecodeMask & 0b001) != 0);
                var classIndexIndex = ReadI32MaybeXor(raw, methodSpecOffset + 4, (methodSpecDecodeMask & 0b010) != 0);
                var methodIndexIndex = ReadI32MaybeXor(raw, methodSpecOffset + 8, (methodSpecDecodeMask & 0b100) != 0);
                var methodSpecFields = new[] { methodDefinitionIndex, classIndexIndex, methodIndexIndex };

                foreach (var permutation in MethodSpecPermutations(allowPermutations))
                {
                    var permutedMethodDefinitionIndex = methodSpecFields[permutation.MethodDefinitionField];
                    var permutedClassIndexIndex = methodSpecFields[permutation.ClassIndexField];
                    var permutedMethodIndexIndex = methodSpecFields[permutation.MethodIndexField];

                    if (permutedMethodDefinitionIndex < 0 || permutedMethodDefinitionIndex >= methodDefCount)
                        continue;

                    foreach (var (normalizedClassIndex, classGenericInstOffset) in EnumerateGenericInstNormalizations(
                                 permutedClassIndexIndex,
                                 genericInstCount,
                                 genericInstOffsets))
                    {
                        foreach (var (normalizedMethodIndex, methodGenericInstOffset) in EnumerateGenericInstNormalizations(
                                     permutedMethodIndexIndex,
                                     genericInstCount,
                                     genericInstOffsets))
                        {
                            var genericInstOffsetFixMask = 0;
                            if (classGenericInstOffset != 0)
                                genericInstOffsetFixMask |= 0b01;
                            if (methodGenericInstOffset != 0)
                                genericInstOffsetFixMask |= 0b10;

                            yield return new GenericMethodRowCandidate(
                                strategy,
                                methodSpecDecodeMask,
                                genericInstOffsetFixMask,
                                classGenericInstOffset,
                                methodGenericInstOffset,
                                permutation.MethodDefinitionField,
                                permutation.ClassIndexField,
                                permutation.MethodIndexField,
                                genericMethodIndex,
                                methodPointerIndex,
                                invokerIndex,
                                adjustorThunk,
                                permutedMethodDefinitionIndex,
                                normalizedClassIndex,
                                normalizedMethodIndex);
                        }
                    }
                }
            }
        }
    }

    private static MethodSpecPermutation[] MethodSpecPermutations(bool allowPermutations)
    {
        return allowPermutations
            ? [
                new MethodSpecPermutation(0, 1, 2),
                new MethodSpecPermutation(1, 0, 2),
                new MethodSpecPermutation(2, 0, 1),
                new MethodSpecPermutation(0, 2, 1),
                new MethodSpecPermutation(1, 2, 0),
                new MethodSpecPermutation(2, 1, 0),
            ]
            : [new MethodSpecPermutation(0, 1, 2)];
    }

    private static int[] MethodSpecDecodeMasks(GenericDecodeStrategy strategy)
    {
        return strategy switch
        {
            GenericDecodeStrategy.RawRaw or GenericDecodeStrategy.TableXorRaw => [0],
            GenericDecodeStrategy.RawMethodSpecXor or GenericDecodeStrategy.TableXorMethodSpecXor => [0b111],
            _ => [0b100, 0b010, 0b110, 0b001, 0b101, 0b011],
        };
    }

    private static IEnumerable<(int Normalized, int Offset)> EnumerateGenericInstNormalizations(
        int value,
        long genericInstCount,
        int[] genericInstOffsets)
    {
        if (value == -1 || (value >= 0 && value < genericInstCount))
        {
            yield return (value, 0);
            yield break;
        }

        foreach (var offset in genericInstOffsets)
        {
            var adjusted = value - offset;
            if (adjusted < 0 || adjusted >= genericInstCount)
                continue;

            yield return (adjusted, offset);
        }
    }

    private static int ReadI32MaybeXor(byte[] raw, long offset, bool decode)
    {
        var value = ReadI32(raw, offset);
        return decode ? unchecked((int)((uint)value ^ CnRecoveryGenericXorMask)) : value;
    }

    private static bool IsGenericMethodSemanticCandidate(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        byte[] raw,
        long genericInstsRaw,
        long genericInstsCount,
        GenericMethodRowCandidate candidate)
    {
        if (candidate.MethodDefinitionIndex < 0 || candidate.MethodDefinitionIndex >= metadata.methodDefs.Length)
            return false;

        try
        {
            var method = metadata.methodDefs[candidate.MethodDefinitionIndex];
            var declaringTypeArity = method.DeclaringType?.GenericContainer?.genericParameterCount ?? 0;
            var methodArity = method.GenericContainer?.genericParameterCount ?? 0;

            if (declaringTypeArity > 0 &&
                GetGenericInstPointerCount(binary, raw, genericInstsRaw, genericInstsCount, candidate.ClassIndexIndex) < declaringTypeArity)
            {
                return false;
            }

            if (candidate.MethodIndexIndex >= 0 &&
                GetGenericInstPointerCount(binary, raw, genericInstsRaw, genericInstsCount, candidate.MethodIndexIndex) < methodArity)
            {
                return false;
            }

            return true;
        }
        catch
        {
            return false;
        }
    }

    private static long GetGenericInstPointerCount(
        Il2CppBinary binary,
        byte[] raw,
        long genericInstsRaw,
        long genericInstsCount,
        int genericInstIndex)
    {
        if (genericInstIndex < 0)
            return 0;
        if (genericInstIndex >= genericInstsCount)
            return -1;

        var ptrOffset = genericInstsRaw + genericInstIndex * PointerSize;
        if (!IsRangeInRaw(raw, ptrOffset, PointerSize))
            return -1;

        var genericInstVa = ReadU64(raw, ptrOffset);
        if (!binary.TryMapVirtualAddressToRaw(genericInstVa, out var genericInstRaw) ||
            !IsRangeInRaw(raw, genericInstRaw, PointerSize * 2))
        {
            return -1;
        }

        return (long)ReadU64(raw, genericInstRaw);
    }

    private static bool IsEnvEnabled(string name)
    {
        var value = Environment.GetEnvironmentVariable(name);
        return value is not null &&
               (value.Equals("1", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("true", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("yes", StringComparison.OrdinalIgnoreCase));
    }

    private static void ClearCustomAttributeRanges(Il2CppMetadata metadata)
    {
        foreach (var image in metadata.imageDefinitions)
        {
            image.customAttributeStart = 0;
            image.customAttributeCount = 0;
        }
    }

    private static void ClearParameterDefaultAttributeBits(
        Il2CppBinary binary,
        Il2CppMetadata metadata,
        Il2CppMetadataRegistration? metadataReg)
    {
        if (metadataReg == null || metadataReg.typeAddressListAddress == 0 || metadataReg.numTypes <= 0)
            return;

        var raw = GetMutableRawBinaryContent(binary);
        var typePtrs = binary.ReadNUintArrayAtVirtualAddress(metadataReg.typeAddressListAddress, metadataReg.numTypes);
        var seenTypeIndices = new HashSet<int>();
        var patched = 0;

        foreach (var method in metadata.methodDefs)
        {
            if (method.parameterCount == 0 || method.parameterStart.IsNull)
                continue;

            for (var i = 0; i < method.parameterCount; i++)
            {
                var parameterIndex = method.parameterStart.Value + i;
                var parameter = metadata.GetParameterDefinitionFromIndex(
                    Il2CppVariableWidthIndex<Il2CppParameterDefinition>.MakeTemporaryForFixedWidthUsage(parameterIndex));
                var typeIndex = parameter.typeIndex.Value;
                if (typeIndex < 0 || typeIndex >= typePtrs.Length || !seenTypeIndices.Add(typeIndex))
                    continue;

                if (!binary.TryMapVirtualAddressToRaw(typePtrs[typeIndex], out var typeRawOffset))
                    continue;

                if (ClearTypeAttributeBits(raw, typeRawOffset, ParameterAttributesHasDefault))
                    patched++;
            }
        }

        Console.WriteLine($"CN metadata recovery shim cleared parameter HasDefault on {patched} Il2CppType rows.");
    }

    private static bool ClearTypeAttributeBits(byte[] raw, long typeRawOffset, uint mask)
    {
        var bitsOffset = typeRawOffset + PointerSize;
        if (bitsOffset < 0 || bitsOffset + sizeof(uint) > raw.Length)
            return false;

        var offset = (int)bitsOffset;
        var bits = BitConverter.ToUInt32(raw, offset);
        if ((bits & mask) == 0)
            return false;

        var updated = bits & ~mask;
        BitConverter.GetBytes(updated).CopyTo(raw, offset);
        return true;
    }

    private static byte[] GetMutableRawBinaryContent(Il2CppBinary binary)
    {
        var type = binary.GetType();
        while (type != null)
        {
            foreach (var fieldName in new[] { "_raw", "raw" })
            {
                var field = type.GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
                if (field?.GetValue(binary) is byte[] raw)
                    return raw;
            }

            type = type.BaseType;
        }

        throw new NotSupportedException($"Unable to locate mutable raw buffer for binary type {binary.GetType().FullName}.");
    }

    private static int EstimateSyntheticBlockSize(IEnumerable<string> names)
    {
        var materializedNames = names.ToArray();
        var nameBytes = materializedNames.Sum(name => Encoding.ASCII.GetByteCount(name) + 1 + 7);
        return Align(Marker.Length, PointerSize)
               + materializedNames.Length * PointerSize
               + PointerSize
               + materializedNames.Length * CodeGenModuleSizeV27_2
               + nameBytes
               + 0x100;
    }

    private static int FindZeroRun(byte[] raw, int bytesNeeded, int alignment)
    {
        var runStart = -1;
        var runLength = 0;

        for (var i = 0; i < raw.Length; i++)
        {
            if (raw[i] == 0)
            {
                if (runStart < 0)
                    runStart = i;
                runLength++;
                if (runLength >= bytesNeeded)
                {
                    var aligned = Align(runStart, alignment);
                    if (i - aligned + 1 >= bytesNeeded)
                        return aligned;
                }
            }
            else
            {
                runStart = -1;
                runLength = 0;
            }
        }

        return -1;
    }

    private static bool TryMapRawToVirtual(Il2CppBinary binary, int rawOffset, out ulong va)
    {
        try
        {
            va = binary.MapRawAddressToVirtual((uint)rawOffset);
            return va != 0;
        }
        catch
        {
            va = 0;
            return false;
        }
    }

    private static int Align(int value, int alignment) => (value + alignment - 1) & ~(alignment - 1);

    private static bool IsRangeInRaw(byte[] raw, long offset, long length) =>
        offset >= 0 && length >= 0 && offset <= raw.LongLength - length;

    private static int ReadI32(byte[] raw, long offset) => BitConverter.ToInt32(raw, (int)offset);

    private static ulong ReadU64(byte[] raw, long offset) => BitConverter.ToUInt64(raw, (int)offset);

    private static void WriteI32(byte[] raw, long offset, int value)
    {
        BitConverter.GetBytes(value).CopyTo(raw, (int)offset);
    }

    private static void WriteU64(byte[] raw, int offset, ulong value)
    {
        for (var i = 0; i < 8; i++)
            raw[offset + i] = (byte)(value >> (i * 8));
    }

    private enum GenericDecodeStrategy
    {
        RawRaw,
        TableXorRaw,
        RawMethodSpecXor,
        TableXorMethodSpecXor,
        RawMethodSpecFieldXor,
        TableXorMethodSpecFieldXor,
    }

    private sealed record GenericMethodRowCandidate(
        GenericDecodeStrategy Strategy,
        int MethodSpecDecodeMask,
        int GenericInstOffsetFixMask,
        int ClassGenericInstOffset,
        int MethodGenericInstOffset,
        int MethodDefinitionField,
        int ClassIndexField,
        int MethodIndexField,
        int GenericMethodIndex,
        int MethodPointerIndex,
        int InvokerIndex,
        int AdjustorThunk,
        int MethodDefinitionIndex,
        int ClassIndexIndex,
        int MethodIndexIndex)
    {
        public string RecoveryKey =>
            $"{Strategy}:{MethodSpecDecodeMask}:{ClassGenericInstOffset:X}:{MethodGenericInstOffset:X}:{MethodDefinitionField}{ClassIndexField}{MethodIndexField}";
    }

    private sealed record MethodSpecPermutation(
        int MethodDefinitionField,
        int ClassIndexField,
        int MethodIndexField);

    private readonly record struct CodeRegistrationCandidate(ulong Va, string Source);
}
