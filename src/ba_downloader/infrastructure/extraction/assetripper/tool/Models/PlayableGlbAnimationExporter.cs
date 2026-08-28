using System.Collections.Concurrent;
using System.Diagnostics.CodeAnalysis;
using System.Numerics;
using System.Text.Json.Nodes;
using AssetRipper.Assets;
using AssetRipper.Export.Modules.Models;
using AssetRipper.Import.Structure.Assembly.Managers;
using AssetRipper.Processing.AnimationClips;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_4;
using AssetRipper.SourceGenerated.Classes.ClassID_74;
using AssetRipper.SourceGenerated.Classes.ClassID_90;
using AssetRipper.SourceGenerated.Classes.ClassID_91;
using AssetRipper.SourceGenerated.Classes.ClassID_93;
using AssetRipper.SourceGenerated.Classes.ClassID_95;
using AssetRipper.SourceGenerated.Classes.ClassID_111;
using AssetRipper.SourceGenerated.Classes.ClassID_137;
using AssetRipper.SourceGenerated.Classes.ClassID_221;
using AssetRipper.SourceGenerated.Extensions;
using AssetRipper.SourceGenerated.Subclasses.AnimationClipOverride;
using AssetRipper.SourceGenerated.Subclasses.FloatCurve;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Quaternionf;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Single;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Vector3f;
using AssetRipper.SourceGenerated.Subclasses.PPtrCurve;
using AssetRipper.SourceGenerated.Subclasses.QuaternionCurve;
using AssetRipper.SourceGenerated.Subclasses.Vector3Curve;
using SharpGLTF.Animations;
using SharpGLTF.Scenes;

namespace Baad.AssetRipper.Models;

internal sealed record AnimationBinding(
	IGameObject Root,
	IAvatar? Avatar,
	IAnimationClip Clip);

/// <summary>
/// Converts only animations referenced by the hierarchy currently being exported.
/// </summary>
public sealed class PlayableGlbAnimationExporter(IAssemblyManager assemblyManager)
	: IPlayableGlbPostProcessor
{
	private readonly ConcurrentDictionary<string, Lazy<bool>> convertedClips = new(StringComparer.Ordinal);

	public void Process(PlayableGlbBuildResult result)
	{
		AnimationBinding[] bindings = CollectBindings(result.Roots);
		if (bindings.Length == 0)
		{
			return;
		}
		JsonArray metadataClips = [];
		HashSet<string> emittedMetadata = new(StringComparer.Ordinal);
		Dictionary<IGameObject, Dictionary<string, ITransform>> transformPaths = [];
		Dictionary<(IGameObject Root, IAvatar? Avatar), PathChecksumCache> checksumCaches = [];
		foreach (AnimationBinding binding in bindings)
		{
			EnsureConverted(binding, GetChecksumCache);
			if (!transformPaths.TryGetValue(binding.Root, out Dictionary<string, ITransform>? transforms))
			{
				transforms = BuildTransformPaths(binding.Root);
				transformPaths.Add(binding.Root, transforms);
			}
			string track = GetTrackName(binding.Clip);
			AddTransformTracks(result.Nodes, transforms, binding.Clip, track);
			AddMorphTracks(result.MorphBindings, transforms, binding.Clip, track);
			bool humanoidBaked = HumanoidAnimationBaker.TryBake(
				result.Nodes,
				transforms,
				binding.Root,
				binding.Avatar,
				binding.Clip,
				track);
			string identity = GetClipIdentity(binding.Clip);
			if (emittedMetadata.Add(identity))
			{
				metadataClips.Add(CreateMetadata(binding.Clip, track, humanoidBaked));
			}
		}
		result.Scene.Extras = new JsonObject
		{
			["BAAD_unity_animation"] = new JsonObject
			{
				["schema_version"] = 0,
				["clips"] = metadataClips,
			},
		};

		PathChecksumCache GetChecksumCache(AnimationBinding binding)
		{
			var key = (binding.Root, binding.Avatar);
			if (!checksumCaches.TryGetValue(key, out PathChecksumCache cache))
			{
				cache = new PathChecksumCache(
					assemblyManager,
					[binding.Root],
					binding.Avatar is null ? [] : [binding.Avatar]);
				checksumCaches.Add(key, cache);
			}
			return cache;
		}
	}

	private void EnsureConverted(
		AnimationBinding binding,
		Func<AnimationBinding, PathChecksumCache> getChecksumCache)
	{
		string identity = GetClipIdentity(binding.Clip);
		_ = convertedClips.GetOrAdd(
			identity,
			_ => new Lazy<bool>(
				() =>
				{
					if (HasRuntimeCurveData(binding.Clip))
					{
						AnimationClipConverter.Process(
							binding.Clip,
							getChecksumCache(binding));
					}
					return true;
				},
				LazyThreadSafetyMode.ExecutionAndPublication)).Value;
	}

	private static bool HasRuntimeCurveData(IAnimationClip clip) =>
		clip.Has_ClipBindingConstant_C74()
		&& clip.ClipBindingConstant_C74 is { } bindings
		&& bindings.GenericBindings.Count > 0;

	private static AnimationBinding[] CollectBindings(IReadOnlyList<IGameObject> roots)
	{
		Dictionary<string, AnimationBinding> bindings = new(StringComparer.Ordinal);
		foreach (IGameObject hierarchyRoot in roots)
		{
			foreach (IUnityObjectBase asset in hierarchyRoot.FetchHierarchy())
			{
				switch (asset)
				{
					case IAnimator animator when animator.GameObjectP is not null:
						foreach (IAnimationClip clip in GetAnimatorClips(animator))
						{
							AnimationBinding binding = new(animator.GameObjectP, animator.AvatarP, clip);
							bindings.TryAdd(GetBindingIdentity(binding), binding);
						}
						break;
					case IAnimation animation when animation.GameObjectP is not null:
						foreach (IAnimationClip clip in GetLegacyClips(animation))
						{
							AnimationBinding binding = new(animation.GameObjectP, null, clip);
							bindings.TryAdd(GetBindingIdentity(binding), binding);
						}
						break;
				}
			}
		}
		return bindings.Values
			.OrderBy(binding => GetBindingIdentity(binding), StringComparer.Ordinal)
			.ToArray();
	}

	private static IEnumerable<IAnimationClip> GetAnimatorClips(IAnimator animator)
	{
		if (animator.Has_Controller_PPtr_RuntimeAnimatorController_5()
			&& animator.Controller_PPtr_RuntimeAnimatorController_5P is { } controller5)
		{
			return GetControllerClips(controller5);
		}
		if (animator.Has_Controller_PPtr_RuntimeAnimatorController_4_3()
			&& animator.Controller_PPtr_RuntimeAnimatorController_4_3P is { } controller43)
		{
			return GetControllerClips(controller43);
		}
		return animator.Controller_PPtr_AnimatorController_4P is { } controller4
			? GetAnimatorControllerClips(controller4)
			: [];
	}

	private static IEnumerable<IAnimationClip> GetControllerClips(IRuntimeAnimatorController controller)
	{
		switch (controller)
		{
			case IAnimatorController animatorController:
				foreach (IAnimationClip clip in GetAnimatorControllerClips(animatorController))
				{
					yield return clip;
				}
				break;
			case IAnimatorOverrideController overrideController:
				foreach (IAnimationClipOverride pair in overrideController.Clips)
				{
					if (pair.OriginalClip.TryGetAsset(controller.Collection) is IAnimationClip original)
					{
						yield return original;
					}
					if (pair.OverrideClip.TryGetAsset(controller.Collection) is IAnimationClip replacement)
					{
						yield return replacement;
					}
				}
				if (overrideController.ControllerP is IRuntimeAnimatorController baseController)
				{
					foreach (IAnimationClip clip in GetControllerClips(baseController))
					{
						yield return clip;
					}
				}
				break;
		}
	}

	private static IEnumerable<IAnimationClip> GetAnimatorControllerClips(
		IAnimatorController controller)
	{
		return controller.AnimationClipsP.WhereNotNull();
	}

	private static IEnumerable<IAnimationClip> GetLegacyClips(IAnimation animation)
	{
		if (animation.AnimationP is IAnimationClip defaultClip)
		{
			yield return defaultClip;
		}
		foreach (IAnimationClip? clip in animation.AnimationsP)
		{
			if (clip is not null)
			{
				yield return clip;
			}
		}
	}

	private static Dictionary<string, ITransform> BuildTransformPaths(IGameObject root)
	{
		Dictionary<string, ITransform> paths = new(StringComparer.Ordinal)
		{
			[string.Empty] = root.GetTransform(),
		};
		AddChildren(root.GetTransform(), string.Empty, paths);
		return paths;

		static void AddChildren(
			ITransform parent,
			string parentPath,
			Dictionary<string, ITransform> paths)
		{
			foreach (ITransform child in parent.Children_C4P.WhereNotNull())
			{
				IGameObject? gameObject = child.GameObject_C4P;
				if (gameObject is null)
				{
					continue;
				}
				string path = string.IsNullOrEmpty(parentPath)
					? gameObject.Name
					: $"{parentPath}/{gameObject.Name}";
				paths.TryAdd(path, child);
				AddChildren(child, path, paths);
			}
		}
	}

	private static void AddTransformTracks(
		IReadOnlyDictionary<ITransform, NodeBuilder> nodes,
		IReadOnlyDictionary<string, ITransform> transforms,
		IAnimationClip clip,
		string track)
	{
		foreach (IVector3Curve curve in clip.PositionCurves_C74)
		{
			if (TryGetNode(nodes, transforms, curve.Path.String, out NodeBuilder? node))
			{
				AddVectorCurve(node.UseTranslation(track), curve, convertPosition: true);
			}
		}
		foreach (IQuaternionCurve curve in clip.RotationCurves_C74)
		{
			if (TryGetNode(nodes, transforms, curve.Path.String, out NodeBuilder? node))
			{
				AddQuaternionCurve(node.UseRotation(track), curve);
			}
		}
		foreach (IVector3Curve curve in clip.ScaleCurves_C74)
		{
			if (TryGetNode(nodes, transforms, curve.Path.String, out NodeBuilder? node))
			{
				AddVectorCurve(node.UseScale(track), curve, convertPosition: false);
			}
		}
	}

	private static bool TryGetNode(
		IReadOnlyDictionary<ITransform, NodeBuilder> nodes,
		IReadOnlyDictionary<string, ITransform> transforms,
		string path,
		[NotNullWhen(true)] out NodeBuilder? node)
	{
		node = null;
		return transforms.TryGetValue(path, out ITransform? transform)
			&& nodes.TryGetValue(transform, out node);
	}

	private static void AddVectorCurve(
		CurveBuilder<Vector3> target,
		IVector3Curve source,
		bool convertPosition)
	{
		foreach (IKeyframe_Vector3f key in source.Curve.Curve)
		{
			Vector3 value = key.Value.CastToStruct();
			Vector3 incoming = key.InSlope.CastToStruct();
			Vector3 outgoing = key.OutSlope.CastToStruct();
			if (!float.IsFinite(key.Time) || !IsFinite(value))
			{
				continue;
			}
			incoming = IsFinite(incoming) ? incoming : Vector3.Zero;
			outgoing = IsFinite(outgoing) ? outgoing : Vector3.Zero;
			if (convertPosition)
			{
				value = ConvertVector(value);
				incoming = ConvertVector(incoming);
				outgoing = ConvertVector(outgoing);
			}
			target.SetPoint(key.Time, value, isLinear: false);
			target.SetIncomingTangent(key.Time, incoming);
			target.SetOutgoingTangent(key.Time, outgoing);
		}
	}

	private static void AddQuaternionCurve(
		CurveBuilder<Quaternion> target,
		IQuaternionCurve source)
	{
		Quaternion? previous = null;
		foreach (IKeyframe_Quaternionf key in source.Curve.Curve)
		{
			Quaternion value = ConvertQuaternion(key.Value.CastToStruct());
			Quaternion incoming = ConvertQuaternionTangent(key.InSlope.CastToStruct());
			Quaternion outgoing = ConvertQuaternionTangent(key.OutSlope.CastToStruct());
			if (
				!float.IsFinite(key.Time)
					|| !IsFinite(value)
					|| value.LengthSquared() <= float.Epsilon)
			{
				continue;
			}
			incoming = IsFinite(incoming) ? incoming : Quaternion.Identity;
			outgoing = IsFinite(outgoing) ? outgoing : Quaternion.Identity;
			if (previous.HasValue && Quaternion.Dot(previous.Value, value) < 0.0f)
			{
				value = Negate(value);
				incoming = Negate(incoming);
				outgoing = Negate(outgoing);
			}
			value = Quaternion.Normalize(value);
			target.SetPoint(key.Time, value, isLinear: false);
			target.SetIncomingTangent(key.Time, incoming);
			target.SetOutgoingTangent(key.Time, outgoing);
			previous = value;
		}
	}

	private static void AddMorphTracks(
		IReadOnlyDictionary<ITransform, GlbMorphBinding> morphBindings,
		IReadOnlyDictionary<string, ITransform> transforms,
		IAnimationClip clip,
		string track)
	{
		Dictionary<
			ITransform,
			(GlbMorphBinding Binding, Dictionary<string, (GlbMorphChannel Channel, IFloatCurve Curve)> Curves)
		> animated = [];
		foreach (IFloatCurve curve in clip.FloatCurves_C74)
		{
			if (
				curve.ClassID != 137
				|| !curve.Attribute.String.StartsWith("blendShape.", StringComparison.Ordinal)
				|| !transforms.TryGetValue(curve.Path.String, out ITransform? transform)
				|| !morphBindings.TryGetValue(transform, out GlbMorphBinding? binding))
			{
				continue;
			}
			string channelName = curve.Attribute.String["blendShape.".Length..];
			GlbMorphChannel? channel = binding.Channels.FirstOrDefault(
				item => item.Name == channelName);
			if (channel is null)
			{
				continue;
			}
			if (!animated.TryGetValue(transform, out var state))
			{
				state = (binding, new(StringComparer.Ordinal));
				animated.Add(transform, state);
			}
			state.Curves.TryAdd(channel.Name, (channel, curve));
		}

		foreach (var state in animated.Values)
		{
			bool requiresSampling = state.Curves.Values.Any(
				item => item.Channel.Frames.Count != 1
					|| item.Curve.Curve.Curve.Any(
						key => !float.IsFinite(key.InSlope) || !float.IsFinite(key.OutSlope)));
			SortedSet<float> sampleTimes = BuildMorphSampleTimes(
				state.Curves.Values.Select(item => item.Curve),
				requiresSampling ? clip.SampleRate_C74 : null);
			if (sampleTimes.Count == 0)
			{
				continue;
			}
			CurveBuilder<ArraySegment<float>> target = state.Binding.Content.UseMorphing(track);
			foreach (float time in sampleTimes)
			{
				float[] weights = state.Binding.InitialWeights.ToArray();
				float[] incoming = new float[weights.Length];
				float[] outgoing = new float[weights.Length];
				foreach ((GlbMorphChannel channel, IFloatCurve curve) in state.Curves.Values)
				{
					PlayableGlbLevelBuilder.SetMorphWeights(
						weights,
						channel,
						HumanoidAnimationBaker.Evaluate(curve, time));
					if (!requiresSampling)
					{
						GlbMorphFrame frame = channel.Frames[0];
						if (frame.FullWeight != 0.0f)
						{
							incoming[frame.TargetIndex] = HumanoidAnimationBaker.EvaluateDerivative(
								curve,
								time,
								incoming: true) / frame.FullWeight;
							outgoing[frame.TargetIndex] = HumanoidAnimationBaker.EvaluateDerivative(
								curve,
								time,
								incoming: false) / frame.FullWeight;
						}
					}
				}
				target.SetPoint(
					time,
					new ArraySegment<float>(weights),
					isLinear: requiresSampling);
				if (!requiresSampling)
				{
					target.SetIncomingTangent(time, new ArraySegment<float>(incoming));
					target.SetOutgoingTangent(time, new ArraySegment<float>(outgoing));
				}
			}
		}
	}

	private static SortedSet<float> BuildMorphSampleTimes(
		IEnumerable<IFloatCurve> curves,
		float? sampleRate)
	{
		IFloatCurve[] materialized = curves.ToArray();
		SortedSet<float> times = new(materialized
			.SelectMany(curve => curve.Curve.Curve)
			.Select(key => key.Time)
			.Where(float.IsFinite));
		if (sampleRate is null || times.Count == 0)
		{
			return times;
		}
		float end = MathF.Max(0.0f, times.Max);
		float rate = float.IsFinite(sampleRate.Value)
			? Math.Clamp(sampleRate.Value, 1.0f, 120.0f)
			: 30.0f;
		int frameCount = Math.Max(1, (int)MathF.Ceiling(end * rate));
		for (int frame = 0; frame <= frameCount; frame++)
		{
			times.Add(MathF.Min(end, frame / rate));
		}
		return times;
	}

	private static JsonObject CreateMetadata(
		IAnimationClip clip,
		string track,
		bool humanoidBaked)
	{
		JsonArray curves = [];
		foreach (IFloatCurve curve in clip.FloatCurves_C74)
		{
			if (
				curve.ClassID == 137
				&& curve.Attribute.String.StartsWith("blendShape.", StringComparison.Ordinal))
			{
				continue;
			}
			JsonArray keys = [];
			foreach (IKeyframe_Single key in curve.Curve.Curve)
			{
				keys.Add(new JsonArray(
					ToJsonNumber(key.Time),
					ToJsonNumber(key.Value),
					ToJsonNumber(key.InSlope),
					ToJsonNumber(key.OutSlope)));
			}
			curves.Add(new JsonObject
			{
				["path"] = curve.Path.String,
				["attribute"] = curve.Attribute.String,
				["class_id"] = curve.ClassID,
				["keys"] = keys,
			});
		}
		JsonArray objectCurves = [];
		if (clip.Has_PPtrCurves_C74())
		{
			foreach (IPPtrCurve curve in clip.PPtrCurves_C74)
			{
				JsonArray keys = [];
				foreach (var key in curve.Curve)
				{
					IUnityObjectBase? value = key.Value.TryGetAsset(clip.Collection);
					keys.Add(new JsonObject
					{
						["time"] = ToJsonNumber(key.Time),
						["collection"] = value?.Collection.Name ?? string.Empty,
						["path_id"] = value?.PathID ?? 0,
					});
				}
				objectCurves.Add(new JsonObject
				{
					["path"] = curve.Path.String,
					["attribute"] = curve.Attribute.String,
					["class_id"] = curve.ClassID,
					["keys"] = keys,
				});
			}
		}
		JsonArray events = [];
		foreach (var item in clip.Events_C74)
		{
			events.Add(new JsonObject
			{
				["time"] = ToJsonNumber(item.Time),
				["function"] = item.FunctionName.String,
				["data"] = item.Data.String,
				["float"] = ToJsonNumber(item.FloatParameter),
				["int"] = item.IntParameter,
			});
		}
		return new JsonObject
		{
			["name"] = clip.Name_C74.String,
			["track"] = track,
			["collection"] = clip.Collection.Name,
			["path_id"] = clip.PathID,
			["sample_rate"] = ToJsonNumber(clip.SampleRate_C74),
			["wrap_mode"] = clip.WrapMode_C74,
			["humanoid_baked"] = humanoidBaked,
			["unity_curves"] = curves,
			["object_curves"] = objectCurves,
			["events"] = events,
		};
	}

	private static string GetTrackName(IAnimationClip clip)
	{
		string name = string.IsNullOrWhiteSpace(clip.Name_C74.String)
			? "AnimationClip"
			: clip.Name_C74.String;
		return $"{name}--{clip.PathID:x}";
	}

	private static string GetBindingIdentity(AnimationBinding binding) =>
		$"{binding.Root.Collection.Name}\n{binding.Root.PathID}\n{GetClipIdentity(binding.Clip)}";

	private static string GetClipIdentity(IAnimationClip clip) =>
		$"{clip.Collection.Name.Replace('\\', '/').Trim().ToLowerInvariant()}\n{clip.PathID}";

	private static Vector3 ConvertVector(Vector3 value) => new(-value.X, value.Y, value.Z);

	private static Quaternion ConvertQuaternion(Quaternion value) =>
		new(value.X, -value.Y, -value.Z, value.W);

	private static Quaternion ConvertQuaternionTangent(Quaternion value) =>
		new(value.X, -value.Y, -value.Z, value.W);

	private static Quaternion Negate(Quaternion value) =>
		new(-value.X, -value.Y, -value.Z, -value.W);

	private static bool IsFinite(Vector3 value) =>
		float.IsFinite(value.X) && float.IsFinite(value.Y) && float.IsFinite(value.Z);

	private static bool IsFinite(Quaternion value) =>
		float.IsFinite(value.X)
			&& float.IsFinite(value.Y)
			&& float.IsFinite(value.Z)
			&& float.IsFinite(value.W);

	private static JsonNode ToJsonNumber(float value) => value switch
	{
		float.NaN => JsonValue.Create("NaN"),
		float.PositiveInfinity => JsonValue.Create("+Infinity"),
		float.NegativeInfinity => JsonValue.Create("-Infinity"),
		_ => JsonValue.Create(value),
	};
}
