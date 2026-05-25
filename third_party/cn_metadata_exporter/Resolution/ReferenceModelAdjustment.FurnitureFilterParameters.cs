using static CnMetadataExporter.TypeNameHelpers;

namespace CnMetadataExporter;

internal sealed partial class ReferenceModelAdjustment
{
    private ResolvedParameterModel[] AdjustFurnitureFilterSecondaryParameters(
        ResolvedMethodModel method,
        ResolvedParameterModel[] adjustedParameters)
    {
            if (isFurnitureFilter)
            {
                if (method.DisplayName == ".ctor")
                {
                    adjustedParameters = adjustedParameters.Select(parameter =>
                    {
                        string? parameterType = parameter.Identifier switch
                        {
                            "rarityList" => BuildListType("FlatData.Rarity"),
                            "tierList" => secureLongListType,
                            "gradeList" => BuildListType("System.Int32"),
                            "categoryList" => furnitureCategoryListType,
                            "subCategoryList" => furnitureSubCategoryListType,
                            _ => null,
                        };

                        return parameterType is null
                            ? parameter
                            : parameter with
                            {
                                TypeName = forceReferenceTypes ? parameterType! : PreferReferenceType(parameter.TypeName, parameterType),
                            };
                    }).ToArray();
                }
                else if (method.DisplayName == "IsShowAfterFiltering")
                {
                    adjustedParameters = adjustedParameters.Select(parameter =>
                        parameter.Identifier is "assetObject" or "P0"
                            ? parameter with { TypeName = assetObjectBaseType! }
                            : parameter).ToArray();
                }
            }

        return adjustedParameters;
    }
}
