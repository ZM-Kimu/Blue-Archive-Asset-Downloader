using System.Diagnostics.CodeAnalysis;
using System.Numerics;
using AssetRipper.Export.Modules.Models;
using AssetRipper.Primitives;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_4;
using AssetRipper.SourceGenerated.Classes.ClassID_74;
using AssetRipper.SourceGenerated.Classes.ClassID_90;
using AssetRipper.SourceGenerated.Classes.ClassID_95;
using AssetRipper.SourceGenerated.Extensions;
using AssetRipper.SourceGenerated.Subclasses.Axes;
using AssetRipper.SourceGenerated.Subclasses.FloatCurve;
using AssetRipper.SourceGenerated.Subclasses.Human;
using AssetRipper.SourceGenerated.Subclasses.Keyframe_Single;
using AssetRipper.SourceGenerated.Subclasses.Vector3Float;
using AssetRipper.SourceGenerated.Subclasses.Vector4Float;
using SharpGLTF.Animations;
using SharpGLTF.Scenes;

namespace Baad.AssetRipper.Models;

internal sealed record HumanoidMuscleBinding(int HumanBone, int Axis);

/// <summary>
/// Bakes referenced Mecanim muscle curves into ordinary glTF bone tracks.
/// </summary>
internal static class HumanoidAnimationBaker
{
	private const int Hips = 0;
	private const int AnimatorClassId = 95;
	private const float MinimumSampleRate = 1.0f;
	private const float MaximumSampleRate = 120.0f;
	private static readonly IReadOnlyDictionary<string, HumanoidMuscleBinding> MuscleBindings =
		CreateMuscleBindings();

	public static bool TryBake(
		IReadOnlyDictionary<ITransform, NodeBuilder> nodes,
		IReadOnlyDictionary<string, ITransform> transforms,
		IGameObject root,
		IAvatar? avatar,
		IAnimationClip clip,
		string track)
	{
		if (avatar is null)
		{
			return false;
		}
		Dictionary<int, IFloatCurve?[]> muscleCurves = CollectMuscleCurves(clip);
		Dictionary<int, IFloatCurve?[]> translationCurves = CollectTranslationCurves(clip);
		IFloatCurve?[] motionTranslation = GetComponentCurves(clip, "MotionT", 3);
		IFloatCurve?[] motionRotation = GetComponentCurves(clip, "MotionQ", 4);
		IFloatCurve?[] bodyTranslation = GetComponentCurves(clip, "RootT", 3);
		IFloatCurve?[] bodyRotation = GetComponentCurves(clip, "RootQ", 4);
		if (
			muscleCurves.Count == 0
			&& translationCurves.Count == 0
			&& motionTranslation.All(curve => curve is null)
			&& motionRotation.All(curve => curve is null)
			&& bodyTranslation.All(curve => curve is null)
			&& bodyRotation.All(curve => curve is null))
		{
			return false;
		}

		Dictionary<int, (ITransform Transform, IAxes Axes)> bones = ResolveBones(
			avatar,
			transforms);
		if (bones.Count == 0)
		{
			return false;
		}
		AddTwistRecipients(muscleCurves);
		IFloatCurve[] bakeCurves = muscleCurves.Values
			.Concat(translationCurves.Values)
			.Append(motionTranslation)
			.Append(motionRotation)
			.Append(bodyTranslation)
			.Append(bodyRotation)
			.SelectMany(curves => curves)
			.WhereNotNull()
			.Distinct()
			.ToArray();
		float[] samples = BuildSampleTimes(clip.SampleRate_C74, bakeCurves);
		IHuman human = avatar.Avatar.Human.Data;
		bool baked = false;
		foreach ((int humanBone, IFloatCurve?[] curves) in muscleCurves)
		{
			if (
				!bones.TryGetValue(humanBone, out var bone)
				|| !nodes.TryGetValue(bone.Transform, out NodeBuilder? node))
			{
				continue;
			}
			CurveBuilder<Quaternion> target = node.UseRotation(track);
			Quaternion? previous = null;
			foreach (float time in samples)
			{
				Vector3 degrees = GetMuscleAngles(bone.Axes, curves, time);
				degrees = RedistributeTwist(
					humanBone,
					degrees,
					human,
					muscleCurves,
					bones,
					time);
				Quaternion value = BakeRotationFromDegrees(bone.Axes, degrees);
				value = ConvertQuaternion(value);
				if (previous.HasValue && Quaternion.Dot(previous.Value, value) < 0.0f)
				{
					value = Negate(value);
				}
				target.SetPoint(time, value, isLinear: true);
				previous = value;
			}
			baked = true;
		}

		foreach ((int humanBone, IFloatCurve?[] curves) in translationCurves)
		{
			if (
				!bones.TryGetValue(humanBone, out var bone)
				|| !nodes.TryGetValue(bone.Transform, out NodeBuilder? node))
			{
				continue;
			}
			CurveBuilder<Vector3> target = node.UseTranslation(track);
			Vector3 reference = bone.Transform.LocalPosition_C4.CastToStruct();
			foreach (float time in samples)
			{
				Vector3 offset = new(
					Evaluate(curves[0], time),
					Evaluate(curves[1], time),
					Evaluate(curves[2], time));
					target.SetPoint(time, ConvertVector(reference + offset), isLinear: true);
			}
			baked = true;
		}

		if (nodes.TryGetValue(root.GetTransform(), out NodeBuilder? rootNode))
		{
			baked |= AddComponentTransformTracks(
				rootNode,
				track,
				samples,
				motionTranslation,
				motionRotation,
				root.GetTransform().LocalPosition_C4.CastToStruct(),
				root.GetTransform().LocalRotation_C4.CastToStruct());
		}
		if (
			bones.TryGetValue(Hips, out var hips)
			&& nodes.TryGetValue(hips.Transform, out NodeBuilder? hipsNode))
		{
			baked |= AddComponentTransformTracks(
				hipsNode,
				track,
				samples,
				bodyTranslation,
				bodyRotation,
				hips.Transform.LocalPosition_C4.CastToStruct(),
				hips.Transform.LocalRotation_C4.CastToStruct());
		}
		return baked;
	}

	internal static Quaternion BakeRotation(IAxes axes, Vector3 muscles) =>
		BakeRotationFromDegrees(axes, GetMuscleAngles(axes, muscles));

	private static Quaternion BakeRotationFromDegrees(IAxes axes, Vector3 degrees)
	{
		Vector3 radians = degrees * (MathF.PI / 180.0f);
		float tx = MathF.Tan(radians.X * 0.5f);
		float ty = MathF.Tan(radians.Y * 0.5f);
		float tz = MathF.Tan(radians.Z * 0.5f);
		Quaternion muscle = Quaternion.Normalize(new Quaternion(
			tx,
			ty + tx * tz,
			tz - tx * ty,
			1.0f));
		Quaternion pre = ToQuaternion(axes.PreQ);
		Quaternion post = ToQuaternion(axes.PostQ);
		return Quaternion.Normalize(pre * muscle * Quaternion.Inverse(post));
	}

	private static Vector3 GetMuscleAngles(
		IAxes axes,
		IReadOnlyList<IFloatCurve?> curves,
		float time) =>
		GetMuscleAngles(
			axes,
			new Vector3(
				Evaluate(curves[0], time),
				Evaluate(curves[1], time),
				Evaluate(curves[2], time)));

	private static Vector3 GetMuscleAngles(IAxes axes, Vector3 muscles)
	{
		Vector3 minimum = GetMinimum(axes);
		Vector3 maximum = GetMaximum(axes);
		Vector3 sign = GetSign(axes);
		return new Vector3(
			ToAngle(muscles.X, minimum.X, maximum.X) * sign.X,
			ToAngle(muscles.Y, minimum.Y, maximum.Y) * sign.Y,
			ToAngle(muscles.Z, minimum.Z, maximum.Z) * sign.Z);
	}

	private static Vector3 RedistributeTwist(
		int humanBone,
		Vector3 degrees,
		IHuman human,
		IReadOnlyDictionary<int, IFloatCurve?[]> muscleCurves,
		IReadOnlyDictionary<int, (ITransform Transform, IAxes Axes)> bones,
		float time)
	{
		float arm = Math.Clamp(human.ArmTwist, 0.0f, 1.0f);
		float forearm = Math.Clamp(human.ForeArmTwist, 0.0f, 1.0f);
		float upperLeg = Math.Clamp(human.UpperLegTwist, 0.0f, 1.0f);
		float leg = Math.Clamp(human.LegTwist, 0.0f, 1.0f);
		return humanBone switch
		{
			14 or 15 => degrees with { Z = degrees.Z * (1.0f - arm) },
			16 => degrees with
			{
				Y = GetTwistAngle(14, 2) * arm + degrees.Y * (1.0f - forearm),
			},
			17 => degrees with
			{
				Y = GetTwistAngle(15, 2) * arm + degrees.Y * (1.0f - forearm),
			},
			18 => degrees with { Z = degrees.Z + GetTwistAngle(16, 1) * forearm },
			19 => degrees with { Z = degrees.Z + GetTwistAngle(17, 1) * forearm },
			1 or 2 => degrees with { Z = degrees.Z * (1.0f - upperLeg) },
			3 => degrees with
			{
				Y = GetTwistAngle(1, 2) * upperLeg + degrees.Y * (1.0f - leg),
			},
			4 => degrees with
			{
				Y = GetTwistAngle(2, 2) * upperLeg + degrees.Y * (1.0f - leg),
			},
			5 => degrees with { Y = degrees.Y + GetTwistAngle(3, 1) * leg },
			6 => degrees with { Y = degrees.Y + GetTwistAngle(4, 1) * leg },
			_ => degrees,
		};

		float GetTwistAngle(int sourceBone, int axis)
		{
			if (
				!muscleCurves.TryGetValue(sourceBone, out IFloatCurve?[]? curves)
				|| !bones.TryGetValue(sourceBone, out var bone))
			{
				return 0.0f;
			}
			Vector3 source = GetMuscleAngles(bone.Axes, curves, time);
			return axis switch { 0 => source.X, 1 => source.Y, _ => source.Z };
		}
	}

	private static void AddTwistRecipients(Dictionary<int, IFloatCurve?[]> curves)
	{
		ReadOnlySpan<(int Source, int Recipient)> transfers =
		[
			(14, 16),
			(15, 17),
			(16, 18),
			(17, 19),
			(1, 3),
			(2, 4),
			(3, 5),
			(4, 6),
		];
		foreach ((int source, int recipient) in transfers)
		{
			if (curves.ContainsKey(source))
			{
				curves.TryAdd(recipient, new IFloatCurve?[3]);
			}
		}
	}

	private static bool AddComponentTransformTracks(
		NodeBuilder node,
		string track,
		IReadOnlyList<float> samples,
		IReadOnlyList<IFloatCurve?> translation,
		IReadOnlyList<IFloatCurve?> rotation,
		Vector3 referenceTranslation,
		Quaternion referenceRotation)
	{
		bool wrote = false;
		if (translation.Any(curve => curve is not null))
		{
			wrote = true;
			CurveBuilder<Vector3> target = node.UseTranslation(track);
			foreach (float time in samples)
			{
				Vector3 value = new(
					EvaluateOrDefault(translation[0], time, referenceTranslation.X),
					EvaluateOrDefault(translation[1], time, referenceTranslation.Y),
					EvaluateOrDefault(translation[2], time, referenceTranslation.Z));
				target.SetPoint(time, ConvertVector(value), isLinear: true);
			}
		}
		if (rotation.Any(curve => curve is not null))
		{
			wrote = true;
			CurveBuilder<Quaternion> target = node.UseRotation(track);
			Quaternion? previous = null;
			foreach (float time in samples)
			{
				Quaternion value = new(
					EvaluateOrDefault(rotation[0], time, referenceRotation.X),
					EvaluateOrDefault(rotation[1], time, referenceRotation.Y),
					EvaluateOrDefault(rotation[2], time, referenceRotation.Z),
					EvaluateOrDefault(rotation[3], time, referenceRotation.W));
				value = value.LengthSquared() == 0.0f
					? Quaternion.Identity
					: Quaternion.Normalize(value);
				value = ConvertQuaternion(value);
				if (previous.HasValue && Quaternion.Dot(previous.Value, value) < 0.0f)
				{
					value = Negate(value);
				}
				target.SetPoint(time, value, isLinear: true);
				previous = value;
			}
		}
		return wrote;
	}

	private static Dictionary<int, IFloatCurve?[]> CollectMuscleCurves(IAnimationClip clip)
	{
		Dictionary<int, IFloatCurve?[]> result = [];
		foreach (IFloatCurve curve in clip.FloatCurves_C74)
		{
			if (
				curve.ClassID != AnimatorClassId
				|| !MuscleBindings.TryGetValue(curve.Attribute.String, out HumanoidMuscleBinding? binding))
			{
				continue;
			}
			if (!result.TryGetValue(binding.HumanBone, out IFloatCurve?[]? axes))
			{
				axes = new IFloatCurve?[3];
				result.Add(binding.HumanBone, axes);
			}
			axes[binding.Axis] = curve;
		}
		return result;
	}

	private static Dictionary<int, IFloatCurve?[]> CollectTranslationCurves(IAnimationClip clip)
	{
		Dictionary<int, IFloatCurve?[]> result = [];
		foreach (IFloatCurve curve in clip.FloatCurves_C74)
		{
			if (curve.ClassID != AnimatorClassId)
			{
				continue;
			}
			string attribute = curve.Attribute.String;
			int marker = attribute.IndexOf("TDOF.", StringComparison.Ordinal);
			if (marker <= 0 || !TryGetHumanBone(attribute[..marker], out int humanBone))
			{
				continue;
			}
			int axis = attribute[^1] switch { 'x' => 0, 'y' => 1, 'z' => 2, _ => -1 };
			if (axis < 0)
			{
				continue;
			}
			if (!result.TryGetValue(humanBone, out IFloatCurve?[]? axes))
			{
				axes = new IFloatCurve?[3];
				result.Add(humanBone, axes);
			}
			axes[axis] = curve;
		}
		return result;
	}

	private static IFloatCurve?[] GetComponentCurves(
		IAnimationClip clip,
		string prefix,
		int count)
	{
		IFloatCurve?[] result = new IFloatCurve?[count];
		foreach (IFloatCurve curve in clip.FloatCurves_C74)
		{
			if (
				curve.ClassID != AnimatorClassId
				|| !curve.Attribute.String.StartsWith(prefix, StringComparison.Ordinal))
			{
				continue;
			}
			int index = curve.Attribute.String[^1] switch
			{
				'x' => 0,
				'y' => 1,
				'z' => 2,
				'w' when count == 4 => 3,
				_ => -1,
			};
			if (index >= 0 && index < count)
			{
				result[index] = curve;
			}
		}
		return result;
	}

	private static Dictionary<int, (ITransform Transform, IAxes Axes)> ResolveBones(
		IAvatar avatar,
		IReadOnlyDictionary<string, ITransform> transforms)
	{
		Dictionary<int, (ITransform, IAxes)> result = [];
		var constant = avatar.Avatar;
		var human = constant.Human.Data;
		var skeleton = constant.AvatarSkeleton.Data;
		for (int humanBone = 0; humanBone < human.HumanBoneIndex.Count; humanBone++)
		{
			int humanNode = human.HumanBoneIndex[humanBone];
			if (
				humanNode < 0
				|| humanNode >= constant.HumanSkeletonIndexArray.Count)
			{
				continue;
			}
			int avatarNode = constant.HumanSkeletonIndexArray[humanNode];
			if (avatarNode < 0 || avatarNode >= skeleton.Node.Count || avatarNode >= skeleton.ID.Count)
			{
				continue;
			}
			int axesId = skeleton.Node[avatarNode].AxesId;
			if (axesId < 0 || axesId >= skeleton.AxesArray.Count)
			{
				continue;
			}
			Utf8String? fullPath = avatar.FindBonePath(skeleton.ID[avatarNode]);
			if (fullPath is null || !TryResolveTransform(transforms, fullPath.String, out ITransform? transform))
			{
				continue;
			}
			result[humanBone] = (transform, skeleton.AxesArray[axesId]);
		}
		return result;
	}

	private static bool TryResolveTransform(
		IReadOnlyDictionary<string, ITransform> transforms,
		string avatarPath,
		[NotNullWhen(true)] out ITransform? transform)
	{
		string normalized = avatarPath.Replace('\\', '/').Trim('/');
		if (transforms.TryGetValue(normalized, out transform))
		{
			return true;
		}
		ITransform[] matches = transforms
			.Where(pair => normalized.EndsWith($"/{pair.Key}", StringComparison.Ordinal))
			.Select(pair => pair.Value)
			.Distinct()
			.Take(2)
			.ToArray();
		transform = matches.Length == 1 ? matches[0] : null;
		return transform is not null;
	}

	private static float[] BuildSampleTimes(
		float sampleRate,
		IReadOnlyList<IFloatCurve> curves)
	{
		float end = curves
			.SelectMany(curve => curve.Curve.Curve)
			.Select(key => key.Time)
			.Where(float.IsFinite)
			.DefaultIfEmpty(0.0f)
			.Max();
		float rate = float.IsFinite(sampleRate)
			? Math.Clamp(sampleRate, MinimumSampleRate, MaximumSampleRate)
			: 30.0f;
		int frameCount = Math.Max(1, (int)MathF.Ceiling(end * rate));
		SortedSet<float> times = [];
		for (int frame = 0; frame <= frameCount; frame++)
		{
			times.Add(MathF.Min(end, frame / rate));
		}
		foreach (IFloatCurve curve in curves)
		{
			foreach (IKeyframe_Single key in curve.Curve.Curve)
			{
				if (float.IsFinite(key.Time))
				{
					times.Add(key.Time);
				}
			}
		}
		return times.ToArray();
	}

	internal static float Evaluate(IFloatCurve? curve, float time)
	{
		if (curve is null || curve.Curve.Curve.Count == 0)
		{
			return 0.0f;
		}
		var keys = curve.Curve.Curve;
		if (time <= keys[0].Time)
		{
			return FiniteOrZero(keys[0].Value);
		}
		if (time >= keys[^1].Time)
		{
			return FiniteOrZero(keys[^1].Value);
		}
		int lower = 1;
		int upper = keys.Count - 1;
		while (lower < upper)
		{
			int middle = lower + (upper - lower) / 2;
			if (keys[middle].Time < time)
			{
				lower = middle + 1;
			}
			else
			{
				upper = middle;
			}
		}
		IKeyframe_Single next = keys[lower];
		IKeyframe_Single previous = keys[lower - 1];
		float duration = next.Time - previous.Time;
		if (
			duration <= 0.0f
				|| !float.IsFinite(previous.OutSlope)
				|| !float.IsFinite(next.InSlope))
		{
			return FiniteOrZero(previous.Value);
		}
		float amount = (time - previous.Time) / duration;
		float amount2 = amount * amount;
		float amount3 = amount2 * amount;
		float h00 = 2.0f * amount3 - 3.0f * amount2 + 1.0f;
		float h10 = amount3 - 2.0f * amount2 + amount;
		float h01 = -2.0f * amount3 + 3.0f * amount2;
		float h11 = amount3 - amount2;
		return FiniteOrZero(h00 * previous.Value
			+ h10 * duration * previous.OutSlope
			+ h01 * next.Value
			+ h11 * duration * next.InSlope);
	}

	internal static float EvaluateDerivative(
		IFloatCurve? curve,
		float time,
		bool incoming)
	{
		if (curve is null || curve.Curve.Curve.Count == 0)
		{
			return 0.0f;
		}
		var keys = curve.Curve.Curve;
		if (time < keys[0].Time || time > keys[^1].Time)
		{
			return 0.0f;
		}
		int lower = 0;
		int upper = keys.Count - 1;
		while (lower < upper)
		{
			int middle = lower + (upper - lower) / 2;
			if (keys[middle].Time < time)
			{
				lower = middle + 1;
			}
			else
			{
				upper = middle;
			}
		}
		IKeyframe_Single next = keys[lower];
		if (next.Time == time)
		{
			float slope = incoming ? next.InSlope : next.OutSlope;
			return float.IsFinite(slope) ? slope : 0.0f;
		}
		if (lower == 0)
		{
			return 0.0f;
		}
		IKeyframe_Single previous = keys[lower - 1];
		float duration = next.Time - previous.Time;
		if (
			duration <= 0.0f
				|| !float.IsFinite(previous.OutSlope)
				|| !float.IsFinite(next.InSlope))
		{
			return 0.0f;
		}
		float amount = (time - previous.Time) / duration;
		float amount2 = amount * amount;
		return FiniteOrZero((
			(6.0f * amount2 - 6.0f * amount) * previous.Value
			+ (3.0f * amount2 - 4.0f * amount + 1.0f)
				* duration
				* previous.OutSlope
			+ (-6.0f * amount2 + 6.0f * amount) * next.Value
			+ (3.0f * amount2 - 2.0f * amount) * duration * next.InSlope
		) / duration);
	}

	private static float EvaluateOrDefault(IFloatCurve? curve, float time, float fallback) =>
		curve is null ? FiniteOrZero(fallback) : Evaluate(curve, time);

	private static float FiniteOrZero(float value) => float.IsFinite(value) ? value : 0.0f;

	private static float ToAngle(float muscle, float minimum, float maximum) =>
		muscle >= 0.0f ? muscle * maximum : -muscle * minimum;

	private static Vector3 GetMinimum(IAxes axes)
	{
		var limit = axes.Limit;
		if (limit.Has_Min_Vector3Float_5_5())
		{
			return ToVector3(limit.Min_Vector3Float_5_5);
		}
		if (limit.Has_Min_Vector3Float_5_4())
		{
			return ToVector3(limit.Min_Vector3Float_5_4);
		}
		return ToVector3(limit.Min_Vector4Float_4);
	}

	private static Vector3 GetMaximum(IAxes axes)
	{
		var limit = axes.Limit;
		if (limit.Has_Max_Vector3Float_5_5())
		{
			return ToVector3(limit.Max_Vector3Float_5_5);
		}
		if (limit.Has_Max_Vector3Float_5_4())
		{
			return ToVector3(limit.Max_Vector3Float_5_4);
		}
		return ToVector3(limit.Max_Vector4Float_4);
	}

	private static Vector3 GetSign(IAxes axes)
	{
		if (axes.Has_Sgn_Vector3Float_5_5())
		{
			return ToVector3(axes.Sgn_Vector3Float_5_5);
		}
		if (axes.Has_Sgn_Vector3Float_5_4())
		{
			return ToVector3(axes.Sgn_Vector3Float_5_4);
		}
		return ToVector3(axes.Sgn_Vector4Float_4);
	}

	private static Vector3 ToVector3(IVector3Float value) =>
		new(value.X, value.Y, value.Z);

	private static Vector3 ToVector3(IVector4Float value) =>
		new(value.X, value.Y, value.Z);

	private static Quaternion ToQuaternion(IVector4Float value) =>
		Quaternion.Normalize(new Quaternion(value.X, value.Y, value.Z, value.W));

	private static Quaternion ConvertQuaternion(Quaternion value) =>
		new(value.X, -value.Y, -value.Z, value.W);

	private static Vector3 ConvertVector(Vector3 value) => new(-value.X, value.Y, value.Z);

	private static Quaternion Negate(Quaternion value) =>
		new(-value.X, -value.Y, -value.Z, -value.W);

	private static bool TryGetHumanBone(string name, out int bone)
	{
		bone = name switch
		{
			"Spine" => 7, "Chest" => 8, "UpperChest" => 9, "Neck" => 10,
			"Head" => 11, "LeftUpperLeg" => 1, "LeftLowerLeg" => 3,
			"LeftFoot" => 5, "LeftToes" => 20, "RightUpperLeg" => 2,
			"RightLowerLeg" => 4, "RightFoot" => 6, "RightToes" => 21,
			"LeftShoulder" => 12, "LeftUpperArm" => 14, "LeftLowerArm" => 16,
			"LeftHand" => 18, "RightShoulder" => 13, "RightUpperArm" => 15,
			"RightLowerArm" => 17, "RightHand" => 19, _ => -1,
		};
		return bone >= 0;
	}

	private static IReadOnlyDictionary<string, HumanoidMuscleBinding> CreateMuscleBindings()
	{
		Dictionary<string, HumanoidMuscleBinding> result = new(StringComparer.Ordinal);
		Add(result, 7, "Spine Front-Back", "Spine Left-Right", "Spine Twist Left-Right");
		Add(result, 8, "Chest Front-Back", "Chest Left-Right", "Chest Twist Left-Right");
		Add(result, 9, "UpperChest Front-Back", "UpperChest Left-Right", "UpperChest Twist Left-Right");
		Add(result, 10, "Neck Nod Down-Up", "Neck Tilt Left-Right", "Neck Turn Left-Right");
		Add(result, 11, "Head Nod Down-Up", "Head Tilt Left-Right", "Head Turn Left-Right");
		Add(result, 22, "Left Eye Down-Up", "Left Eye In-Out");
		Add(result, 23, "Right Eye Down-Up", "Right Eye In-Out");
		Add(result, 24, "Jaw Close", "Jaw Left-Right");
		Add(result, 1, "Left Upper Leg Front-Back", "Left Upper Leg In-Out", "Left Upper Leg Twist In-Out");
		Add(result, 3, "Left Lower Leg Stretch", "Left Lower Leg Twist In-Out");
		Add(result, 5, "Left Foot Up-Down", "Left Foot Twist In-Out");
		Add(result, 20, "Left Toes Up-Down");
		Add(result, 2, "Right Upper Leg Front-Back", "Right Upper Leg In-Out", "Right Upper Leg Twist In-Out");
		Add(result, 4, "Right Lower Leg Stretch", "Right Lower Leg Twist In-Out");
		Add(result, 6, "Right Foot Up-Down", "Right Foot Twist In-Out");
		Add(result, 21, "Right Toes Up-Down");
		Add(result, 12, "Left Shoulder Down-Up", "Left Shoulder Front-Back");
		Add(result, 14, "Left Arm Down-Up", "Left Arm Front-Back", "Left Arm Twist In-Out");
		Add(result, 16, "Left Forearm Stretch", "Left Forearm Twist In-Out");
		Add(result, 18, "Left Hand Down-Up", "Left Hand In-Out");
		Add(result, 13, "Right Shoulder Down-Up", "Right Shoulder Front-Back");
		Add(result, 15, "Right Arm Down-Up", "Right Arm Front-Back", "Right Arm Twist In-Out");
		Add(result, 17, "Right Forearm Stretch", "Right Forearm Twist In-Out");
		Add(result, 19, "Right Hand Down-Up", "Right Hand In-Out");
		AddFingerBindings(result, "LeftHand", 25);
		AddFingerBindings(result, "RightHand", 40);
		return result;
	}

	private static void Add(
		Dictionary<string, HumanoidMuscleBinding> target,
		int humanBone,
		params string[] names)
	{
		for (int axis = 0; axis < names.Length; axis++)
		{
			target.Add(names[axis], new HumanoidMuscleBinding(humanBone, axis));
		}
	}

	private static void AddFingerBindings(
		Dictionary<string, HumanoidMuscleBinding> target,
		string hand,
		int firstBone)
	{
		string[] fingers = ["Thumb", "Index", "Middle", "Ring", "Little"];
		for (int finger = 0; finger < fingers.Length; finger++)
		{
			int proximal = firstBone + finger * 3;
			target.Add($"{hand}.{fingers[finger]}.1 Stretched", new(proximal, 0));
			target.Add($"{hand}.{fingers[finger]}.Spread", new(proximal, 1));
			target.Add($"{hand}.{fingers[finger]}.2 Stretched", new(proximal + 1, 0));
			target.Add($"{hand}.{fingers[finger]}.3 Stretched", new(proximal + 2, 0));
		}
	}
}
