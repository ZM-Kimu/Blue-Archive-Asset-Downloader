using System.Numerics;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using AssetRipper.Assets;
using AssetRipper.Assets.Bundles;
using AssetRipper.Assets.Collections;
using AssetRipper.Assets.Metadata;
using AssetRipper.Export.Modules.Models;
using AssetRipper.Export.PrimaryContent;
using AssetRipper.IO.Files;
using AssetRipper.Numerics;
using AssetRipper.Primitives;
using AssetRipper.SourceGenerated;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_137;
using AssetRipper.SourceGenerated.Classes.ClassID_4;
using AssetRipper.SourceGenerated.Classes.ClassID_43;
using AssetRipper.SourceGenerated.Classes.ClassID_74;
using AssetRipper.SourceGenerated.Classes.ClassID_90;
using AssetRipper.SourceGenerated.Classes.ClassID_91;
using AssetRipper.SourceGenerated.Classes.ClassID_93;
using AssetRipper.SourceGenerated.Classes.ClassID_95;
using AssetRipper.SourceGenerated.Enums;
using AssetRipper.SourceGenerated.Extensions;
using AssetRipper.SourceGenerated.Subclasses.FloatCurve;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Single;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Vector3f;
using AssetRipper.SourceGenerated.Subclasses.Vector3Curve;
using SharpGLTF.Schema2;
using Baad.AssetRipper.Models;
using Baad.AssetRipper.PrimaryContent;

if (args.Length != 1)
{
	throw new InvalidDataException("The output directory is required.");
}

string outputRoot = Path.GetFullPath(args[0]);
Directory.CreateDirectory(outputRoot);
ExportTrackingFileSystem fileSystem = new(LocalFileSystem.Instance);

byte[] sequentialPayload = "sequential-write"u8.ToArray();
string sequentialPath = Path.Combine(outputRoot, "sequential.bin");
using (Stream stream = fileSystem.File.Create(sequentialPath))
{
	stream.Write(sequentialPayload);
}
AssertMetadata(fileSystem, sequentialPath, sequentialPayload);

string seekPath = Path.Combine(outputRoot, "seek.bin");
using (Stream stream = fileSystem.File.Create(seekPath))
{
	stream.Write("abc"u8);
	stream.Position = 0;
	stream.Write("x"u8);
}
AssertMetadata(fileSystem, seekPath, "xbc"u8);

byte[] directPayload = "direct-write"u8.ToArray();
string directPath = Path.Combine(outputRoot, "direct.bin");
fileSystem.File.WriteAllBytes(directPath, directPayload);
AssertMetadata(fileSystem, directPath, directPayload);

string textPath = Path.Combine(outputRoot, "text.txt");
fileSystem.File.WriteAllText(textPath, "tracked text".AsSpan());
AssertMetadata(fileSystem, textPath, "tracked text"u8);

string mixedSeparatorPath = outputRoot + "/mixed/path.bin";
Directory.CreateDirectory(Path.GetDirectoryName(mixedSeparatorPath)!);
fileSystem.File.WriteAllBytes(mixedSeparatorPath, directPayload);
AssertMetadata(fileSystem, Path.GetFullPath(mixedSeparatorPath), directPayload);
AssertPlayableGlb(Path.Combine(outputRoot, "playable.glb"));

static void AssertPlayableGlb(string path)
{
	UnityVersion version = new(2022, 3, 21);
	using GameBundle bundle = new();
	ProcessedAssetCollection collection = bundle.AddNewProcessedCollection("PlayableFixture", version);
	IGameObject root = Create<IGameObject>(ClassIDType.GameObject);
	ITransform transform = Create<ITransform>(ClassIDType.Transform);
	IGameObject spine = Create<IGameObject>(ClassIDType.GameObject);
	ITransform spineTransform = Create<ITransform>(ClassIDType.Transform);
	IGameObject body = Create<IGameObject>(ClassIDType.GameObject);
	ITransform bodyTransform = Create<ITransform>(ClassIDType.Transform);
	IGameObject auxiliaryRoot = Create<IGameObject>(ClassIDType.GameObject);
	ITransform auxiliaryTransform = Create<ITransform>(ClassIDType.Transform);
	ISkinnedMeshRenderer renderer = Create<ISkinnedMeshRenderer>(ClassIDType.SkinnedMeshRenderer);
	IMesh mesh = Create<IMesh>(ClassIDType.Mesh);
	IAnimator animator = Create<IAnimator>(ClassIDType.Animator);
	IAnimatorController controller = Create<IAnimatorController>(ClassIDType.AnimatorController);
	IAvatar avatar = Create<IAvatar>(ClassIDType.Avatar);
	IAnimationClip clip = Create<IAnimationClip>(ClassIDType.AnimationClip);

	root.Name = "AnimatedRoot";
	root.AddComponent(ClassIDType.Transform, transform);
	root.AddComponent(ClassIDType.Animator, animator);
	transform.GameObject_C4.SetAsset(collection, root);
	transform.InitializeDefault();
	spine.Name = "Spine";
	spine.AddComponent(ClassIDType.Transform, spineTransform);
	spineTransform.GameObject_C4.SetAsset(collection, spine);
	spineTransform.InitializeDefault();
	spineTransform.Father_C4.SetAsset(collection, transform);
	transform.Children_C4.AddNew().SetAsset(collection, spineTransform);
	body.Name = "Body";
	body.AddComponent(ClassIDType.Transform, bodyTransform);
	body.AddComponent(ClassIDType.SkinnedMeshRenderer, renderer);
	bodyTransform.GameObject_C4.SetAsset(collection, body);
	bodyTransform.InitializeDefault();
	bodyTransform.Father_C4.SetAsset(collection, transform);
	transform.Children_C4.AddNew().SetAsset(collection, bodyTransform);
	auxiliaryRoot.Name = "Spine";
	auxiliaryRoot.AddComponent(ClassIDType.Transform, auxiliaryTransform);
	auxiliaryTransform.GameObject_C4.SetAsset(collection, auxiliaryRoot);
	auxiliaryTransform.InitializeDefault();
	renderer.GameObjectP = body;
	renderer.MeshP = mesh;
	renderer.RootBoneP = spineTransform;
	renderer.Bones.AddNew().SetAsset(collection, spineTransform);
	renderer.Bones.AddNew().SetAsset(collection, auxiliaryTransform);
	renderer.BlendShapeWeights.Add(25.0f);
	renderer.BlendShapeWeights.Add(50.0f);
	ConfigureMesh(mesh);
	animator.GameObjectP = root;
	animator.AvatarP = avatar;
	animator.Controller_PPtr_RuntimeAnimatorController_5P = (IRuntimeAnimatorController)controller;
	controller.AnimationClips.AddNew().SetAsset(collection, clip);
	ConfigureAvatar(avatar);
	clip.Name_C74 = "Move";
	clip.SampleRate_C74 = 30.0f;
	IVector3Curve curve = clip.PositionCurves_C74.AddNew();
	curve.SetValues(string.Empty);
	AddKey(curve, 0.0f, 0.0f);
	AddKey(curve, 1.0f, 2.0f);
	curve.Curve.Curve[1].OutSlope.X = float.PositiveInfinity;
	IFloatCurve muscle = clip.FloatCurves_C74.AddNew();
	muscle.Path = string.Empty;
	muscle.Attribute = "Spine Front-Back";
	muscle.ClassID = (int)ClassIDType.Animator;
	AddMuscleKey(muscle, 0.0f, 0.0f);
	AddMuscleKey(muscle, 1.0f, 1.0f);
	IFloatCurve blendShape = clip.FloatCurves_C74.AddNew();
	blendShape.Path = "Body";
	blendShape.Attribute = "blendShape.Smile";
	blendShape.ClassID = (int)ClassIDType.SkinnedMeshRenderer;
	AddMuscleKey(blendShape, 0.0f, 0.0f);
	AddMuscleKey(blendShape, 1.0f, 100.0f);
	IFloatCurve secondBlendShape = clip.FloatCurves_C74.AddNew();
	secondBlendShape.Path = "Body";
	secondBlendShape.Attribute = "blendShape.Blink";
	secondBlendShape.ClassID = (int)ClassIDType.SkinnedMeshRenderer;
	AddMuscleKey(secondBlendShape, 0.5f, 50.0f);
	AddMuscleKey(secondBlendShape, 1.0f, 0.0f);
	IFloatCurve unityOnly = clip.FloatCurves_C74.AddNew();
	unityOnly.Path = string.Empty;
	unityOnly.Attribute = "BAAD_TestUnityOnly";
	unityOnly.ClassID = (int)ClassIDType.Animator;
	AddMuscleKey(unityOnly, 0.0f, 0.0f);
	AddMuscleKey(unityOnly, 10.0f, 1.0f);
	AddMuscleKey(unityOnly, 11.0f, float.PositiveInfinity);

	WritePlayableGlb(path);
	string repeatedPath = Path.ChangeExtension(path, ".repeat.glb");
	WritePlayableGlb(repeatedPath);
	if (!File.ReadAllBytes(path).AsSpan().SequenceEqual(File.ReadAllBytes(repeatedPath)))
	{
		throw new InvalidDataException("The playable GLB output is not deterministic.");
	}
	ModelRoot model = ModelRoot.Load(path);
	if (!model.LogicalNodes.Any(node => node.Name == "Spine_0"))
	{
		throw new InvalidDataException("The playable GLB did not disambiguate armature node names.");
	}
	if (model.LogicalAnimations.Count != 1)
	{
		throw new InvalidDataException("The playable GLB did not retain its animation track.");
	}
	string[] animatedNodes = model.LogicalAnimations[0].Channels
		.Select(channel => channel.TargetNode.Name)
		.Order(StringComparer.Ordinal)
		.ToArray();
	if (!animatedNodes.Contains("AnimatedRoot") || !animatedNodes.Contains("Spine"))
	{
		throw new InvalidDataException("The playable GLB did not retain transform and Humanoid animation.");
	}
	AnimationChannel spineChannel = model.LogicalAnimations[0].Channels.Single(
		channel => channel.TargetNode.Name == "Spine"
			&& channel.TargetNodePath == PropertyPath.rotation);
	if (spineChannel.GetRotationSampler().GetLinearKeys().Count() != 31)
	{
		throw new InvalidDataException("An unrelated Unity curve expanded the Humanoid bake range.");
	}
	AnimationChannel? morphChannel = model.LogicalAnimations[0].Channels.FirstOrDefault(
		channel => channel.TargetNode.Name == "Body"
			&& channel.TargetNodePath == PropertyPath.weights);
	if (morphChannel is null)
	{
		throw new InvalidDataException("The playable GLB did not retain its BlendShape animation.");
	}
	float[] morphValue = morphChannel
		.GetMorphSampler()
		.CreateCurveSampler()
		.GetPoint(0.5f);
	if (
		morphValue.Length != 2
		|| MathF.Abs(morphValue[0] - 0.5f) >= 0.0001f
		|| MathF.Abs(morphValue[1] - 0.5f) >= 0.0001f)
	{
		throw new InvalidDataException("The playable GLB did not combine BlendShape channels.");
	}
	if (
		model.LogicalSkins.Count != 1
		|| model.LogicalSkins[0].JointsCount != 2
		|| !model.LogicalMeshes.Any(
			mesh => mesh.Primitives.Any(primitive => primitive.MorphTargetsCount == 2)))
	{
		throw new InvalidDataException("The playable GLB did not retain skin and BlendShape geometry.");
	}
	JsonNode? metadata = model.DefaultScene.Extras?["BAAD_unity_animation"];
	JsonNode? metadataClip = metadata?["clips"]?[0];
	if (
		metadataClip?["humanoid_baked"]?.GetValue<bool>() != true
		|| metadataClip["unity_curves"] is not JsonArray unityCurves
		|| !unityCurves.Any(
			item => item?["attribute"]?.GetValue<string>() == "Spine Front-Back")
		|| !unityCurves.Any(
			item => item?["attribute"]?.GetValue<string>() == "BAAD_TestUnityOnly")
		|| unityCurves
			.Single(item => item?["attribute"]?.GetValue<string>() == "BAAD_TestUnityOnly")?
			["keys"]?[2]?[1]?.GetValue<string>() != "+Infinity")
	{
		throw new InvalidDataException("The playable GLB did not retain Unity animation metadata.");
	}

	void WritePlayableGlb(string destination)
	{
		PlayableGlbBuildResult result = PlayableGlbLevelBuilder.Build(
			[root, auxiliaryRoot],
			isScene: false);
		new PlayableGlbAnimationExporter(null!).Process(result);
		using Stream stream = LocalFileSystem.Instance.File.Create(destination);
		if (!GlbWriter.TryWrite(result.Scene, stream, out string? error))
		{
			throw new InvalidDataException(error);
		}
	}

	T Create<T>(ClassIDType classId) where T : class, IUnityObjectBase =>
		collection.CreateAsset(
			(int)classId,
			assetInfo => AssetFactory.CreateSerialized(assetInfo, version) as T
				?? throw new InvalidDataException($"Could not create {classId}."));

	static void AddKey(IVector3Curve target, float time, float x)
	{
		IKeyframe_Vector3f key = target.Curve.Curve.AddNew();
		key.Time = time;
		key.Value.X = x;
		key.Value.Y = 0.0f;
		key.Value.Z = 0.0f;
		key.InSlope.SetZero();
		key.OutSlope.SetZero();
	}

	static void AddMuscleKey(IFloatCurve target, float time, float value)
	{
		IKeyframe_Single key = target.Curve.Curve.AddNew();
		key.Time = time;
		key.Value = value;
		key.InSlope = 0.0f;
		key.OutSlope = 0.0f;
	}

	static void ConfigureAvatar(IAvatar avatar)
	{
		const uint spineHash = 0x51A9E001;
		for (int humanBone = 0; humanBone <= 7; humanBone++)
		{
			avatar.Avatar.Human.Data.HumanBoneIndex.Add(humanBone == 7 ? 0 : -1);
		}
		avatar.Avatar.HumanSkeletonIndexArray.Add(0);
		var skeleton = avatar.Avatar.AvatarSkeleton.Data;
		var node = skeleton.Node.AddNew();
		node.AxesId = 0;
		node.ParentId = -1;
		skeleton.ID.Add(spineHash);
		var axes = skeleton.AxesArray.AddNew();
		axes.PreQ.W = 1.0f;
		axes.PostQ.W = 1.0f;
		axes.Sgn_Vector3Float_5_5.X = 1.0f;
		axes.Sgn_Vector3Float_5_5.Y = 1.0f;
		axes.Sgn_Vector3Float_5_5.Z = 1.0f;
		axes.Limit.Min_Vector3Float_5_5.X = -30.0f;
		axes.Limit.Min_Vector3Float_5_5.Y = -30.0f;
		axes.Limit.Min_Vector3Float_5_5.Z = -30.0f;
		axes.Limit.Max_Vector3Float_5_5.X = 30.0f;
		axes.Limit.Max_Vector3Float_5_5.Y = 30.0f;
		axes.Limit.Max_Vector3Float_5_5.Z = 30.0f;
		avatar.TOS.Add(spineHash, "AnimatedRoot/Spine");
	}

	static void ConfigureMesh(IMesh mesh)
	{
		Vector3[] vertices =
		[
			new(0.0f, 0.0f, 0.0f),
			new(1.0f, 0.0f, 0.0f),
			new(0.0f, 1.0f, 0.0f),
		];
		Vector3[] normals =
		[
			new(0.0f, 0.0f, 1.0f),
			new(0.0f, 0.0f, 1.0f),
			new(0.0f, 0.0f, 1.0f),
		];
		BoneWeight4[] skin =
		[
			new(1.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0),
			new(1.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0),
			new(1.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0),
		];
		uint[] indices = [0, 1, 2];
		SubMeshData[] subMeshes =
		[
			new(
				0,
				0,
				0,
				indices.Length,
				1,
				3,
				MeshTopology.Triangles,
				new Bounds(
					new Vector3(0.5f, 0.5f, 0.0f),
					new Vector3(0.5f, 0.5f, 0.0f))),
		];
		mesh.Name = "SkinnedTriangle";
		mesh.FillWithCompressedMeshData(new MeshData(
			vertices,
			normals,
			null,
			null,
			null,
			null,
			null,
			null,
			null,
			null,
			null,
			null,
			skin,
			[Matrix4x4.Identity, Matrix4x4.Identity],
			indices,
			subMeshes));
		var channel = mesh.Shapes.Channels.AddNew();
		channel.SetValues("Smile", 0, 1);
		var secondChannel = mesh.Shapes.Channels.AddNew();
		secondChannel.SetValues("Blink", 1, 1);
		var shape = mesh.Shapes.Shapes.AddNew();
		shape.FirstVertex = 0;
		shape.VertexCount = 1;
		shape.HasNormals = true;
		var secondShape = mesh.Shapes.Shapes.AddNew();
		secondShape.FirstVertex = 1;
		secondShape.VertexCount = 1;
		secondShape.HasNormals = true;
		var delta = mesh.Shapes.Vertices.AddNew();
		delta.Index = 0;
		delta.Vertex.X = 0.25f;
		delta.Normal.X = 0.1f;
		var secondDelta = mesh.Shapes.Vertices.AddNew();
		secondDelta.Index = 1;
		secondDelta.Vertex.Y = 0.25f;
		secondDelta.Normal.Y = 0.1f;
		mesh.Shapes.FullWeights.Add(100.0f);
		mesh.Shapes.FullWeights.Add(100.0f);
	}
}

static void AssertMetadata(
	ExportTrackingFileSystem fileSystem,
	string path,
	ReadOnlySpan<byte> expected)
{
	if (!fileSystem.TryGetMetadata(path, out ExportedFileMetadata? metadata))
	{
		throw new InvalidDataException("Tracked file metadata was not registered.");
	}
	string expectedHash = Convert.ToHexString(SHA256.HashData(expected)).ToLowerInvariant();
	if (
		metadata.Size != expected.Length
		|| metadata.Sha256 != expectedHash
		|| !File.ReadAllBytes(path).AsSpan().SequenceEqual(expected))
	{
		throw new InvalidDataException("Tracked file metadata does not match its content.");
	}
}
