from __future__ import annotations

import html
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_SOURCE = (
    REPO_ROOT
    / "third_party"
    / "cn_metadata_exporter"
    / "Resolution"
    / "FlatBufferTypeRecovery.cs"
)
FORMATTER_SIDECAR_SOURCE = (
    REPO_ROOT
    / "third_party"
    / "cn_metadata_exporter"
    / "Exporting"
    / "MemoryPackFormatterSidecarWriter.cs"
)
RESOLVED_MODELS_SOURCE = (
    REPO_ROOT
    / "third_party"
    / "cn_metadata_exporter"
    / "Models"
    / "ResolvedExportModels.cs"
)


def test_flatbuffer_type_recovery_maps_known_cn_metadata_gaps(tmp_path: Path) -> None:
    project_dir = tmp_path / "probe"
    project_dir.mkdir()

    source_path = html.escape(str(RECOVERY_SOURCE), quote=True)
    (project_dir / "RecoveryProbe.csproj").write_text(
        f"""
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="{source_path}" Link="FlatBufferTypeRecovery.cs" />
  </ItemGroup>
</Project>
""".strip(),
        encoding="utf-8",
    )
    (project_dir / "Program.cs").write_text(
        """
using YldaDumpCsExporter;

static void Equal(string? actual, string? expected, string caseName)
{
    if (!string.Equals(actual, expected, StringComparison.Ordinal))
    {
        throw new InvalidOperationException($"{caseName}: expected {expected ?? "<null>"}, got {actual ?? "<null>"}");
    }
}

var typeNames = new HashSet<string>(StringComparer.Ordinal)
{
    "FlatData.AniStateData",
    "FlatData.AniEventData",
    "FlatData.BlendData",
    "FlatData.BlendInfo",
    "FlatData.Form",
    "FlatData.GroundNodeFlat",
    "FlatData.GroundNodeFlatNew",
    "FlatData.Motion",
    "FlatData.MoveEnd",
    "FlatData.Position",
    "FlatData.PropMotion",
    "FlatData.PropVector3",
    "FlatData.Sample",
    "FlatData.ValidExisting",
    "GroundVector3",
    "GroundVector3New",
};

Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.AnimatorData", "DataList", typeNames),
    "FlatData.AniStateData",
    "AnimatorData.DataList");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.AniStateData", "Events", typeNames),
    "FlatData.AniEventData",
    "AniStateData.Events");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.AnimationBlendTable", "DataList", typeNames),
    "FlatData.BlendData",
    "AnimationBlendTable.DataList");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.GroundGridFlat", "Nodes", typeNames),
    "FlatData.GroundNodeFlat",
    "GroundGridFlat.Nodes");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.GroundNodeFlat", "Position", typeNames),
    "GroundVector3",
    "GroundNodeFlat.Position");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.GroundGridFlatNew", "Nodes", typeNames),
    "FlatData.GroundNodeFlatNew",
    "GroundGridFlatNew.Nodes");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.GroundNodeFlatNew", "Position", typeNames),
    "GroundVector3New",
    "GroundNodeFlatNew.Position");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.PropRootMotionFlat", "RootMotions", typeNames),
    "FlatData.PropMotion",
    "PropRootMotionFlat.RootMotions");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.RootMotionFlat", "MoveLeft", typeNames),
    "FlatData.Motion",
    "RootMotionFlat.MoveLeft");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.Motion", "Positions", typeNames),
    "FlatData.Position",
    "Motion.Positions");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.SampleTable", "DataList", typeNames),
    "FlatData.Sample",
    "SampleTable.DataList");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.MissingTable", "DataList", typeNames),
    null,
    "MissingTable.DataList");
Equal(
    FlatBufferTypeRecovery.ResolveMemberElementType("FlatData.RootMotionFlat", "MoveLeft", new HashSet<string>()),
    null,
    "missing target validation");

Equal(
    FlatBufferTypeRecovery.PreferFlatBufferType("Type_0x00004F4E", "FlatData.Motion", typeNames),
    "FlatData.Motion",
    "weak Type_0x replacement");
Equal(
    FlatBufferTypeRecovery.PreferFlatBufferType("FlatData.AnimationBlend", "FlatData.BlendData", typeNames),
    "FlatData.BlendData",
    "missing FlatData replacement");
Equal(
    FlatBufferTypeRecovery.PreferFlatBufferType("FlatData.ValidExisting", "FlatData.Motion", typeNames),
    "FlatData.ValidExisting",
    "valid existing type preservation");
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "dotnet",
            "run",
            "--project",
            str(project_dir / "RecoveryProbe.csproj"),
            "-c",
            "Release",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_memorypack_formatter_sidecar_writer_exports_known_cn_dao_layouts(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "formatter_probe"
    project_dir.mkdir()

    sidecar_source_path = html.escape(str(FORMATTER_SIDECAR_SOURCE), quote=True)
    models_source_path = html.escape(str(RESOLVED_MODELS_SOURCE), quote=True)
    (project_dir / "FormatterProbe.csproj").write_text(
        f"""
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="{sidecar_source_path}" Link="MemoryPackFormatterSidecarWriter.cs" />
    <Compile Include="{models_source_path}" Link="ResolvedExportModels.cs" />
  </ItemGroup>
</Project>
""".strip(),
        encoding="utf-8",
    )
    sidecar_path = project_dir / "memorypack_formatters.json"
    escaped_sidecar_path = (
        str(sidecar_path)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )
    (project_dir / "Program.cs").write_text(
        f"""
using System.Text.Json;
using YldaDumpCsExporter;

static ResolvedExportMethodModel Deserialize(uint token)
    => new(token, "Deserialize", "void", ["public", "virtual"], ExportMemberAccessibility.Public, 9, []);

static ResolvedExportTypeModel Type(
    int typeIndex,
    uint token,
    string fullName,
    string? declaringType,
    string? baseType,
    ResolvedExportMethodModel[] methods)
    => new(
        typeIndex,
        token,
        fullName,
        "Assembly-CSharp.dll",
        "-",
        fullName.Split('.').Last(),
        null,
        [],
        [],
        declaringType,
        baseType,
        [],
        [],
        [],
        [],
        [],
        methods);

var artifact = new ResolvedExportArtifact(
    "probe",
    [],
    new TypeIndexArtifact(new Dictionary<uint, string>(), new Dictionary<int, Dictionary<uint, string>>()),
    new RelationshipIndexArtifact(new Dictionary<int, RelationshipIndexEntry>()),
    new MemberIndexArtifact([
        Type(
            1,
            0x02003998,
            "SkillVisualDAOFormatter",
            "MX.AppData.DAO.Battle.SkillVisualDAO",
            "MemoryPack.MemoryPackFormatter<MX.AppData.DAO.Battle.SkillVisualDAO>",
            [Deserialize(0x0601BC7A)]),
        Type(
            2,
            0x02003935,
            "SkillLogicDAOFormatter",
            "MX.GameData.DAO.Battle.SkillLogicDAO",
            "MemoryPack.MemoryPackFormatter<MX.GameData.DAO.Battle.SkillLogicDAO>",
            [Deserialize(0x0601BAAF)]),
        Type(
            3,
            0x02000010,
            "UnknownFormatter",
            "Sample.Unknown",
            "MemoryPack.MemoryPackFormatter<Sample.Unknown>",
            [Deserialize(0x06000010)]),
    ]));

MemoryPackFormatterSidecarWriter.Write(artifact, "{escaped_sidecar_path}");

using var document = JsonDocument.Parse(File.ReadAllText("{escaped_sidecar_path}"));
var formatters = document.RootElement.GetProperty("formatters").EnumerateArray().ToArray();

JsonElement Find(string targetType)
    => formatters.Single(formatter => formatter.GetProperty("target_type").GetString() == targetType);

var skillVisual = Find("MX.AppData.DAO.Battle.SkillVisualDAO");
if (skillVisual.GetProperty("kind").GetString() != "object")
    throw new InvalidOperationException("SkillVisualDAO should export as object layout.");
if (!skillVisual.GetProperty("object_header").GetBoolean())
    throw new InvalidOperationException("SkillVisualDAO should declare an object header.");
var members = skillVisual.GetProperty("members").EnumerateArray().ToArray();
if (members.Length != 8)
    throw new InvalidOperationException($"Expected 8 SkillVisualDAO members, got {{members.Length}}.");
if (members[0].GetProperty("name").GetString() != "name" ||
    members[0].GetProperty("cs_type").GetString() != "string")
    throw new InvalidOperationException("SkillVisualDAO name should be exported as string.");
if (skillVisual.GetProperty("formatter_token").GetString() != "0x02003998")
    throw new InvalidOperationException("Formatter token was not preserved.");
if (skillVisual.GetProperty("method_token").GetString() != "0x0601BC7A")
    throw new InvalidOperationException("Deserialize method token was not preserved.");

var skillLogic = Find("MX.GameData.DAO.Battle.SkillLogicDAO");
if (skillLogic.GetProperty("kind").GetString() != "union" ||
    skillLogic.GetProperty("tag_type").GetString() != "byte")
    throw new InvalidOperationException("SkillLogicDAO should be marked as a byte-tag union.");
if (!skillLogic.GetProperty("reason").GetString()!.Contains("Union tag mapping"))
    throw new InvalidOperationException("SkillLogicDAO should explain missing union tags.");

var unknown = Find("Sample.Unknown");
if (unknown.GetProperty("kind").GetString() != "unresolved")
    throw new InvalidOperationException("Unknown formatter should remain unresolved.");
if (!unknown.GetProperty("reason").GetString()!.Contains("method body analysis"))
    throw new InvalidOperationException("Unknown formatter should explain missing method body analysis.");
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "dotnet",
            "run",
            "--project",
            str(project_dir / "FormatterProbe.csproj"),
            "-c",
            "Release",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
