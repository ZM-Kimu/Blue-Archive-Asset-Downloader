namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private string ResolveAdjustedDisplayName(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            var adjustedDisplayName = method.DisplayName;
            if (isRuntimeInspectorUtils)
            {
                adjustedDisplayName = method.DisplayName switch
                {
                    "IsEmptyForDev" => "IsEmptyForDev<T>",
                    "GetAssignableObjectFromDraggedReferenceItem" when adjustedParameters.Length == 1 => "GetAssignableObjectFromDraggedReferenceItem<T>",
                    "GetAssignableObjectsFromDraggedReferenceItem" when adjustedParameters.Length == 1 => "GetAssignableObjectsFromDraggedReferenceItem<T>",
                    "HasAttribute" => "HasAttribute<T>",
                    "GetAttribute" => "GetAttribute<T>",
                    "GetAttributes" => "GetAttributes<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isHubConnectionExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x060004EF => "GetUpAndDownStreamController<TResult, T1>",
                    0x060004F0 => "GetUpAndDownStreamController<TResult, T1>",
                    0x060004F1 => "GetUpAndDownStreamController<TResult, T1, T2>",
                    0x060004F2 => "GetUpAndDownStreamController<TResult, T1, T2>",
                    0x060004F3 => "GetUpAndDownStreamController<TResult, T1, T2, T3>",
                    0x060004F4 => "GetUpAndDownStreamController<TResult, T1, T2, T3>",
                    0x060004F5 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4>",
                    0x060004F6 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4>",
                    0x060004F7 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x060004F8 => "GetUpAndDownStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x060004F9 => "GetUpStreamController<TResult, T1>",
                    0x060004FA => "GetUpStreamController<TResult, T1>",
                    0x060004FB => "GetUpStreamController<TResult, T1, T2>",
                    0x060004FC => "GetUpStreamController<TResult, T1, T2>",
                    0x060004FD => "GetUpStreamController<TResult, T1, T2, T3>",
                    0x060004FE => "GetUpStreamController<TResult, T1, T2, T3>",
                    0x060004FF => "GetUpStreamController<TResult, T1, T2, T3, T4>",
                    0x06000500 => "GetUpStreamController<TResult, T1, T2, T3, T4>",
                    0x06000501 => "GetUpStreamController<TResult, T1, T2, T3, T4, T5>",
                    0x06000502 => "GetUpStreamController<TResult, T1, T2, T3, T4, T5>",
                    _ => method.DisplayName,
                };
            }
            else if (isUploadItemControllerExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000503 => "UploadParam<TResult, P1>",
                    0x06000504 => "UploadParam<TResult, P1, P2>",
                    0x06000505 => "UploadParam<TResult, P1, P2, P3>",
                    0x06000506 => "UploadParam<TResult, P1, P2, P3, P4>",
                    0x06000507 => "UploadParam<TResult, P1, P2, P3, P4, P5>",
                    _ => method.DisplayName,
                };
            }
            else if (isSystemRuntimeUnsafe)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000001 => "ReadUnaligned<T>",
                    0x06000002 => "WriteUnaligned<T>",
                    0x06000003 => "AsPointer<T>",
                    0x06000004 => "SizeOf<T>",
                    0x06000006 => "As<T>",
                    0x06000007 => "AsRef<T>",
                    0x06000008 => "AsRef<T>",
                    0x06000009 => "As<TFrom, TTo>",
                    0x0600000A => "Add<T>",
                    0x0600000B => "Add<T>",
                    0x0600000C => "AddByteOffset<T>",
                    0x0600000D => "ByteOffset<T>",
                    0x0600000E => "AreSame<T>",
                    0x0600000F => "IsAddressLessThan<T>",
                    0x06000010 => "IsNullRef<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isCommunityToolkitArrayExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000008 => "DangerousGetReference<T>",
                    0x06000009 => "DangerousGetReferenceAt<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isTimelineExtensions)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600038E => "FindTimelineForBone<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isJsonUtility)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000005 => "FromJson<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isSignalRCoreEncoder)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x06000511 => "Encode<T>",
                    0x06000512 => "DecodeAs<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isSignalRCoreUploadItemController)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x060005BD => "UploadParam<T>",
                    _ => method.DisplayName,
                };
            }
            else if (isFutureCallback)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600425A => ".ctor",
                    0x0600425B => "Invoke",
                    0x0600425C => "BeginInvoke",
                    0x0600425D => "EndInvoke",
                    _ => method.DisplayName,
                };
            }
            else if (isFutureValueCallback)
            {
                adjustedDisplayName = method.Definition.Token switch
                {
                    0x0600425E => ".ctor",
                    0x0600425F => "Invoke",
                    0x06004260 => "BeginInvoke",
                    0x06004261 => "EndInvoke",
                    _ => method.DisplayName,
                };
            }

        return adjustedDisplayName;
    }
}
