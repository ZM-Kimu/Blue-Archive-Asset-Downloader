using System.Numerics;
using System.Text.Json.Nodes;
using AssetRipper.Assets;
using AssetRipper.Assets.Collections;
using AssetRipper.Assets.Generics;
using AssetRipper.Export.Modules.Textures;
using AssetRipper.Numerics;
using AssetRipper.Primitives;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_2;
using AssetRipper.SourceGenerated.Classes.ClassID_18;
using AssetRipper.SourceGenerated.Classes.ClassID_21;
using AssetRipper.SourceGenerated.Classes.ClassID_25;
using AssetRipper.SourceGenerated.Classes.ClassID_28;
using AssetRipper.SourceGenerated.Classes.ClassID_33;
using AssetRipper.SourceGenerated.Classes.ClassID_4;
using AssetRipper.SourceGenerated.Classes.ClassID_43;
using AssetRipper.SourceGenerated.Classes.ClassID_137;
using AssetRipper.SourceGenerated.Extensions;
using AssetRipper.SourceGenerated.Subclasses.BlendShapeVertex;
using AssetRipper.SourceGenerated.Subclasses.MeshBlendShape;
using AssetRipper.SourceGenerated.Subclasses.MeshBlendShapeChannel;
using AssetRipper.SourceGenerated.Subclasses.PPtr_Material;
using AssetRipper.SourceGenerated.Subclasses.SubMesh;
using AssetRipper.SourceGenerated.Subclasses.UnityTexEnv;
using SharpGLTF.Geometry;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Materials;
using SharpGLTF.Memory;
using SharpGLTF.Scenes;
using SharpGLTF.Transforms;

namespace AssetRipper.Export.Modules.Models;

public sealed record GlbMorphFrame(int TargetIndex, float FullWeight);

public sealed record GlbMorphChannel(string Name, IReadOnlyList<GlbMorphFrame> Frames);

public sealed record GlbMorphBinding(
	ContentTransformer Content,
	IReadOnlyList<GlbMorphChannel> Channels,
	IReadOnlyList<float> InitialWeights);

public sealed record PlayableGlbBuildResult(
	SceneBuilder Scene,
	IReadOnlyList<IGameObject> Roots,
	IReadOnlyDictionary<ITransform, NodeBuilder> Nodes,
	IReadOnlyDictionary<ITransform, GlbMorphBinding> MorphBindings);

/// <summary>
/// Builds a GLB hierarchy without flattening skinned meshes into rigid geometry.
/// </summary>
public static class PlayableGlbLevelBuilder
{
	public static PlayableGlbBuildResult Build(IEnumerable<IUnityObjectBase> assets, bool isScene)
	{
		IGameObject[] roots = assets
			.Where(asset => asset is IGameObject or IComponent)
			.Select(GetRoot)
			.Distinct()
			.OrderBy(root => root.Name.String, StringComparer.Ordinal)
			.ThenBy(root => root.PathID)
			.ToArray();
		SceneBuilder scene = new();
		Dictionary<ITransform, NodeBuilder> nodes = [];
		Dictionary<ITransform, GlbMorphBinding> morphBindings = [];
		BuildParameters parameters = new(isScene);
		NodeNameAllocator nodeNames = new();
		List<NodeBuilder> rootNodes = [];

		foreach (IGameObject root in roots)
		{
			ITransform transform = root.GetTransform();
			NodeBuilder rootNode = AddTransformHierarchy(
				nodes,
				nodeNames,
				null,
				transform,
				isScene);
			rootNodes.Add(rootNode);
		}
		if (rootNodes.Count == 1)
		{
			scene.AddNode(rootNodes[0]);
		}
		else if (rootNodes.Count > 1)
		{
			NodeBuilder commonRoot = new(nodeNames.Allocate("BAAD_CollectionRoot"));
			foreach (NodeBuilder rootNode in rootNodes)
			{
				commonRoot.AddNode(rootNode);
			}
			scene.AddNode(commonRoot);
		}

		foreach (IGameObject root in roots)
		{
			foreach (IGameObject gameObject in root.FetchHierarchy().OfType<IGameObject>())
			{
				AddRenderable(scene, parameters, nodes, morphBindings, gameObject);
			}
		}

		return new PlayableGlbBuildResult(scene, roots, nodes, morphBindings);
	}

	private static NodeBuilder AddTransformHierarchy(
		Dictionary<ITransform, NodeBuilder> nodes,
		NodeNameAllocator nodeNames,
		NodeBuilder? parent,
		ITransform transform,
		bool preserveRootTransform)
	{
		IGameObject? gameObject = transform.GameObject_C4P;
		if (gameObject is null)
		{
			throw new InvalidDataException("A model transform has no GameObject.");
		}
		NodeBuilder node = parent is null
			? new NodeBuilder(nodeNames.Allocate(gameObject.Name))
			: parent.CreateNode(nodeNames.Allocate(gameObject.Name));
		if (parent is not null || preserveRootTransform)
		{
			node.LocalTransform = new AffineTransform(
				transform.LocalScale_C4.CastToStruct(),
				GlbCoordinateConversion.ToGltfQuaternionConvert(transform.LocalRotation_C4),
				GlbCoordinateConversion.ToGltfVector3Convert(transform.LocalPosition_C4));
		}
		nodes.Add(transform, node);
		foreach (ITransform child in transform.Children_C4P.WhereNotNull())
		{
			AddTransformHierarchy(
				nodes,
				nodeNames,
				node,
				child,
				preserveRootTransform: true);
		}
		return node;
	}

	private static void AddRenderable(
		SceneBuilder scene,
		BuildParameters parameters,
		IReadOnlyDictionary<ITransform, NodeBuilder> nodes,
		Dictionary<ITransform, GlbMorphBinding> morphBindings,
		IGameObject gameObject)
	{
		ITransform transform = gameObject.GetTransform();
		NodeBuilder node = nodes[transform];
		if (gameObject.TryGetComponent(out ISkinnedMeshRenderer? skinnedRenderer))
		{
			AddSkinnedMesh(scene, parameters, nodes, morphBindings, node, transform, skinnedRenderer);
			return;
		}
		if (
			!gameObject.TryGetComponent(out IMeshFilter? meshFilter)
			|| !meshFilter.TryGetMesh(out IMesh? mesh)
			|| !mesh.IsSet()
			|| !gameObject.TryGetComponent(out IRenderer? renderer)
			|| !parameters.TryGetOrMakeMeshData(mesh, out MeshData meshData))
		{
			return;
		}

		Transformation global = GetGlobalTransform(transform);
		Transformation inverse = GetGlobalInverseTransform(transform);
		int[] subsetIndices = GetSubsetIndices(renderer);
		IMeshBuilder<MaterialBuilder> builder = BuildMesh(
			parameters,
			mesh,
			meshData,
			renderer,
			subsetIndices,
			ReferencesDynamicMesh(renderer) ? Transformation.Identity : inverse,
			ReferencesDynamicMesh(renderer) ? Transformation.Identity : global,
			out IReadOnlyList<GlbMorphChannel> channels);
		InstanceBuilder instance = scene.AddRigidMesh(builder, node);
		float[] initialWeights = ApplyInitialMorphWeights(
			instance.Content,
			renderer as ISkinnedMeshRenderer,
			channels);
		if (channels.Count > 0)
		{
			morphBindings[transform] = new GlbMorphBinding(
				instance.Content,
				channels,
				initialWeights);
		}
	}

	private static void AddSkinnedMesh(
		SceneBuilder scene,
		BuildParameters parameters,
		IReadOnlyDictionary<ITransform, NodeBuilder> nodes,
		Dictionary<ITransform, GlbMorphBinding> morphBindings,
		NodeBuilder node,
		ITransform transform,
		ISkinnedMeshRenderer renderer)
	{
		IMesh? mesh = renderer.MeshP;
		if (mesh is null || !mesh.IsSet() || !parameters.TryGetOrMakeMeshData(mesh, out MeshData meshData))
		{
			return;
		}
		ITransform?[] bones = renderer.BonesP.ToArray();
		if (
			!meshData.HasSkin
			|| meshData.BindPose is null
			|| bones.Length == 0
			|| bones.Length != meshData.BindPose.Length
			|| bones.Any(bone => bone is null || !nodes.ContainsKey(bone)))
		{
			throw new InvalidDataException($"Skinned mesh '{mesh.Name}' has an invalid bone binding.");
		}
		IMeshBuilder<MaterialBuilder> builder = BuildMesh(
			parameters,
			mesh,
			meshData,
			renderer,
			Enumerable.Range(0, mesh.SubMeshes.Count).ToArray(),
			Transformation.Identity,
			Transformation.Identity,
			out IReadOnlyList<GlbMorphChannel> channels);
		(NodeBuilder, Matrix4x4)[] bindings = new (NodeBuilder, Matrix4x4)[bones.Length];
		for (int index = 0; index < bones.Length; index++)
		{
			bindings[index] = (
				nodes[bones[index]!],
				ToGltfMatrix(meshData.BindPose[index]));
		}
		InstanceBuilder instance = scene.AddSkinnedMesh(builder, bindings).WithName(node.Name);
		float[] initialWeights = ApplyInitialMorphWeights(instance.Content, renderer, channels);
		if (channels.Count > 0)
		{
			morphBindings[transform] = new GlbMorphBinding(
				instance.Content,
				channels,
				initialWeights);
		}
	}

	private static IMeshBuilder<MaterialBuilder> BuildMesh(
		BuildParameters parameters,
		IMesh mesh,
		MeshData meshData,
		IRenderer renderer,
		int[] subsetIndices,
		Transformation inverseTransform,
		Transformation transform,
		out IReadOnlyList<GlbMorphChannel> channels)
	{
		(ISubMesh, MaterialBuilder)[] subMeshes = new (ISubMesh, MaterialBuilder)[subsetIndices.Length];
		MaterialList materials = new(renderer);
		for (int index = 0; index < subsetIndices.Length; index++)
		{
			subMeshes[index] = (
				mesh.SubMeshes[subsetIndices[index]],
				parameters.GetOrMakeMaterial(materials[index]));
		}
		IMeshBuilder<MaterialBuilder> builder = GlbSubMeshBuilder.BuildSubMeshes(
			new ArraySegment<(ISubMesh, MaterialBuilder)>(subMeshes),
			mesh.Is16BitIndices(),
			meshData,
			transform,
			inverseTransform);
		channels = AddBlendShapes(builder, mesh, meshData, transform, inverseTransform);
		return builder;
	}

	private static IReadOnlyList<GlbMorphChannel> AddBlendShapes(
		IMeshBuilder<MaterialBuilder> builder,
		IMesh mesh,
		MeshData meshData,
		Transformation transform,
		Transformation inverseTransform)
	{
		if (!mesh.Has_Shapes() || mesh.Shapes.Channels.Count == 0)
		{
			return [];
		}
		Transformation deltaTransform = transform.RemoveTranslation();
		Transformation normalTransform = inverseTransform.Transpose();
		List<GlbMorphChannel> channels = [];
		JsonArray targetNames = [];
		int targetIndex = 0;
		foreach (IMeshBlendShapeChannel channel in mesh.Shapes.Channels)
		{
			List<GlbMorphFrame> frames = [];
			for (int frameOffset = 0; frameOffset < channel.FrameCount; frameOffset++)
			{
				int frameIndex = channel.FrameIndex + frameOffset;
				IMeshBlendShape shape = mesh.Shapes.Shapes[frameIndex];
				IMorphTargetBuilder target = builder.UseMorphTarget(targetIndex);
				for (uint vertexOffset = 0; vertexOffset < shape.VertexCount; vertexOffset++)
				{
					IBlendShapeVertex delta = mesh.Shapes.Vertices[(int)(shape.FirstVertex + vertexOffset)];
					if (delta.Index >= meshData.Vertices.Length)
					{
						throw new InvalidDataException($"Blend shape '{channel.Name_R}' references an invalid vertex.");
					}
					Vector3 basePosition = GlbCoordinateConversion.ToGltfVector3Convert(
						meshData.Vertices[delta.Index] * transform);
					Vector3 positionDelta = GlbCoordinateConversion.ToGltfVector3Convert(
						delta.Vertex.CastToStruct() * deltaTransform);
					Vector3 normalDelta = GlbCoordinateConversion.ToGltfVector3Convert(
						delta.Normal.CastToStruct() * normalTransform);
					Vector3 tangentDelta = GlbCoordinateConversion.ToGltfVector3Convert(
						delta.Tangent.CastToStruct() * deltaTransform);
					target.SetVertexDelta(
						basePosition,
						new VertexGeometryDelta(positionDelta, normalDelta, tangentDelta));
				}
			float fullWeight = mesh.Shapes.FullWeights.Count > frameIndex
					? mesh.Shapes.FullWeights[frameIndex]
					: 100.0f;
				fullWeight = float.IsFinite(fullWeight) ? fullWeight : 100.0f;
				frames.Add(new GlbMorphFrame(targetIndex, fullWeight));
				targetNames.Add(channel.FrameCount == 1
					? channel.Name_R.String
					: $"{channel.Name_R.String}@{fullWeight:G9}");
				targetIndex++;
			}
			channels.Add(new GlbMorphChannel(channel.Name_R.String, frames));
		}
		builder.Extras = new JsonObject { ["targetNames"] = targetNames };
		return channels;
	}

	private static float[] ApplyInitialMorphWeights(
		ContentTransformer content,
		ISkinnedMeshRenderer? renderer,
		IReadOnlyList<GlbMorphChannel> channels)
	{
		if (channels.Count == 0)
		{
			return [];
		}
		float[] weights = new float[channels.Sum(channel => channel.Frames.Count)];
		for (int channelIndex = 0; channelIndex < channels.Count; channelIndex++)
		{
			float value = renderer is not null && renderer.BlendShapeWeights.Count > channelIndex
				? renderer.BlendShapeWeights[channelIndex]
				: 0.0f;
			SetMorphWeights(weights, channels[channelIndex], value);
		}
		content.UseMorphing().Value = new ArraySegment<float>(weights);
		return weights;
	}

	public static void SetMorphWeights(Span<float> target, GlbMorphChannel channel, float value)
	{
		if (channel.Frames.Count == 0)
		{
			return;
		}
		value = float.IsFinite(value) ? value : 0.0f;
		GlbMorphFrame first = channel.Frames[0];
		if (value <= first.FullWeight || channel.Frames.Count == 1)
		{
			target[first.TargetIndex] = first.FullWeight == 0.0f ? 0.0f : value / first.FullWeight;
			return;
		}
		for (int index = 1; index < channel.Frames.Count; index++)
		{
			GlbMorphFrame previous = channel.Frames[index - 1];
			GlbMorphFrame current = channel.Frames[index];
			if (value <= current.FullWeight)
			{
				float range = current.FullWeight - previous.FullWeight;
				float amount = range == 0.0f ? 1.0f : (value - previous.FullWeight) / range;
				target[previous.TargetIndex] = 1.0f - amount;
				target[current.TargetIndex] = amount;
				return;
			}
		}
		GlbMorphFrame last = channel.Frames[^1];
		target[last.TargetIndex] = last.FullWeight == 0.0f ? 0.0f : value / last.FullWeight;
	}

	private static Transformation GetGlobalTransform(ITransform transform)
	{
		Transformation result = Transformation.Identity;
		for (ITransform? current = transform; current is not null; current = current.Father_C4P)
		{
			result = current.ToTransformation() * result;
		}
		return result;
	}

	private static Matrix4x4 ToGltfMatrix(Matrix4x4 value)
	{
		Matrix4x4 conversion = Matrix4x4.CreateScale(-1.0f, 1.0f, 1.0f);
		return conversion * value * conversion;
	}

	private static Transformation GetGlobalInverseTransform(ITransform transform)
	{
		Transformation result = Transformation.Identity;
		for (ITransform? current = transform; current is not null; current = current.Father_C4P)
		{
			result *= current.ToInverseTransformation();
		}
		return result;
	}

	private static IGameObject GetRoot(IUnityObjectBase asset) => asset switch
	{
		IGameObject gameObject => gameObject.GetRoot(),
		IComponent component => component.GameObject_C2P?.GetRoot()
			?? throw new InvalidDataException("A model component has no GameObject."),
		_ => throw new InvalidOperationException(),
	};

	private static bool ReferencesDynamicMesh(IRenderer renderer) =>
		renderer.Has_StaticBatchInfo_C25() && renderer.StaticBatchInfo_C25.SubMeshCount == 0
		|| renderer.Has_SubsetIndices_C25() && renderer.SubsetIndices_C25.Count == 0;

	private static int[] GetSubsetIndices(IRenderer renderer)
	{
		if (renderer.Has_SubsetIndices_C25())
		{
			return renderer.SubsetIndices_C25.Select(index => (int)index).ToArray();
		}
		if (renderer.Has_StaticBatchInfo_C25())
		{
			return Enumerable.Range(
				renderer.StaticBatchInfo_C25.FirstSubMesh,
				renderer.StaticBatchInfo_C25.SubMeshCount).ToArray();
		}
		return [];
	}

	private sealed class BuildParameters(bool isScene)
	{
		private readonly MaterialBuilder defaultMaterial = new("DefaultMaterial");
		private readonly Dictionary<ITexture2D, MemoryImage> imageCache = [];
		private readonly Dictionary<IMaterial, MaterialBuilder> materialCache = [];
		private readonly Dictionary<IMesh, MeshData> meshCache = [];

		public bool IsScene { get; } = isScene;

		public bool TryGetOrMakeMeshData(IMesh mesh, out MeshData meshData)
		{
			if (meshCache.TryGetValue(mesh, out meshData))
			{
				return true;
			}
			if (!MeshData.TryMakeFromMesh(mesh, out meshData))
			{
				return false;
			}
			meshCache.Add(mesh, meshData);
			return true;
		}

		public MaterialBuilder GetOrMakeMaterial(IMaterial? material)
		{
			if (material is null)
			{
				return defaultMaterial;
			}
			if (materialCache.TryGetValue(material, out MaterialBuilder? existing))
			{
				return existing;
			}
			MaterialBuilder result = new(material.Name);
			GetTextures(material, out ITexture2D? main, out ITexture2D? normal);
			if (main is not null && TryGetOrMakeImage(main, out MemoryImage mainImage))
			{
				result.WithBaseColor(mainImage);
			}
			if (normal is not null && TryGetOrMakeImage(normal, out MemoryImage normalImage))
			{
				result.WithNormal(normalImage);
			}
			materialCache.Add(material, result);
			return result;
		}

		private bool TryGetOrMakeImage(ITexture2D texture, out MemoryImage image)
		{
			if (imageCache.TryGetValue(texture, out image))
			{
				return true;
			}
			if (!TextureConverter.TryConvertToBitmap(texture, out DirectBitmap bitmap))
			{
				return false;
			}
			using MemoryStream stream = new();
			bitmap.SaveAsPng(stream);
			image = new MemoryImage(stream.ToArray());
			imageCache.Add(texture, image);
			return true;
		}

		private static void GetTextures(
			IMaterial material,
			out ITexture2D? mainTexture,
			out ITexture2D? normalTexture)
		{
			mainTexture = null;
			normalTexture = null;
			ITexture2D? replacement = null;
			foreach ((Utf8String name, IUnityTexEnv parameter) in material.GetTextureProperties())
			{
				string value = name.String;
				if (value is "_MainTex" or "texture" or "Texture" or "_Texture")
				{
					mainTexture ??= parameter.Texture.TryGetAsset(material.Collection) as ITexture2D;
				}
				else if (value is "_Normal" or "Normal" or "normal")
				{
					normalTexture ??= parameter.Texture.TryGetAsset(material.Collection) as ITexture2D;
				}
				else
				{
					replacement ??= parameter.Texture.TryGetAsset(material.Collection) as ITexture2D;
				}
			}
			mainTexture ??= replacement;
		}
	}

	private sealed class NodeNameAllocator
	{
		private readonly Dictionary<string, int> nextSuffix = new(StringComparer.Ordinal);
		private readonly HashSet<string> used = new(StringComparer.Ordinal);

		public string Allocate(string? name)
		{
			string baseName = string.IsNullOrWhiteSpace(name) ? "GameObject" : name;
			if (used.Add(baseName))
			{
				return baseName;
			}
			int suffix = nextSuffix.GetValueOrDefault(baseName);
			string candidate;
			do
			{
				candidate = $"{baseName}_{suffix}";
				suffix++;
			}
			while (!used.Add(candidate));
			nextSuffix[baseName] = suffix;
			return candidate;
		}
	}

	private readonly struct MaterialList(IRenderer renderer)
	{
		private readonly AccessListBase<IPPtr_Material> materials = renderer.Materials_C25;
		private readonly AssetCollection collection = renderer.Collection;

		public IMaterial? this[int index] => index >= materials.Count
			? null
			: materials[index].TryGetAsset(collection);
	}
}
