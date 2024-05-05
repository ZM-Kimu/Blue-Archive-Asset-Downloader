from lib.TableEncryptionService import *

def dump_table(obj) -> list:
    typ_name = obj.__class__.__name__[:-5]
    dump_func = next(f for x,f in globals().items() if x.endswith(typ_name))
    password = CreateKey(typ_name[:-5])
    return [
        dump_func(obj.DataList(j), password)
        for j in range(obj.DataListLength())
    ]

def dump_GroundVector3(obj, password) -> dict:
    return {
        'X': ConvertFloat(obj.X(), password),
        'Y': ConvertFloat(obj.Y(), password),
        'Z': ConvertFloat(obj.Z(), password),
    }

def dump_AcademyFavorScheduleExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'ScheduleGroupId': ConvertLong(obj.ScheduleGroupId(), password),
        'OrderInGroup': ConvertLong(obj.OrderInGroup(), password),
        'Location': ConvertString(obj.Location(), password),
        'LocalizeScenarioId': ConvertUInt(obj.LocalizeScenarioId(), password),
        'FavorRank': ConvertLong(obj.FavorRank(), password),
        'SecretStoneAmount': ConvertLong(obj.SecretStoneAmount(), password),
        'ScenarioSriptGroupId': ConvertLong(obj.ScenarioSriptGroupId(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardAmount': [ConvertLong(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_AcademyLocationExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'PrefabPath': ConvertString(obj.PrefabPath(), password),
        'IconImagePath': ConvertString(obj.IconImagePath(), password),
        'OpenCondition': [School(ConvertInt(obj.OpenCondition(j), password)).name for j in range(obj.OpenConditionLength())],
        'OpenConditionCount': [ConvertLong(obj.OpenConditionCount(j), password) for j in range(obj.OpenConditionCountLength())],
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'OpenTeacherRank': ConvertLong(obj.OpenTeacherRank(), password),
    }

def dump_AcademyLocationRankExcel(obj, password) -> dict:
    return {
        'Rank': ConvertLong(obj.Rank(), password),
        'RankExp': ConvertLong(obj.RankExp(), password),
        'TotalExp': ConvertLong(obj.TotalExp(), password),
    }

def dump_AcademyMessanger1Excel(obj, password) -> dict:
    return {
        'MessageGroupId': ConvertLong(obj.MessageGroupId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MessageCondition': AcademyMessageConditions(ConvertInt(obj.MessageCondition(), password)).name,
        'ConditionValue': ConvertLong(obj.ConditionValue(), password),
        'PreConditionGroupId': ConvertLong(obj.PreConditionGroupId(), password),
        'PreConditionFavorScheduleId': ConvertLong(obj.PreConditionFavorScheduleId(), password),
        'FavorScheduleId': ConvertLong(obj.FavorScheduleId(), password),
        'NextGroupId': ConvertLong(obj.NextGroupId(), password),
        'FeedbackTimeMillisec': ConvertLong(obj.FeedbackTimeMillisec(), password),
        'MessageType': AcademyMessageTypes(ConvertInt(obj.MessageType(), password)).name,
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'MessageKR': ConvertString(obj.MessageKR(), password),
        'MessageJP': ConvertString(obj.MessageJP(), password),
        'MessageTH': ConvertString(obj.MessageTH(), password),
        'MessageTW': ConvertString(obj.MessageTW(), password),
        'MessageEN': ConvertString(obj.MessageEN(), password),
        'MessageDE': ConvertString(obj.MessageDE(), password),
        'MessageFR': ConvertString(obj.MessageFR(), password),
    }

def dump_AcademyMessanger2Excel(obj, password) -> dict:
    return {
        'MessageGroupId': ConvertLong(obj.MessageGroupId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MessageCondition': AcademyMessageConditions(ConvertInt(obj.MessageCondition(), password)).name,
        'ConditionValue': ConvertLong(obj.ConditionValue(), password),
        'PreConditionGroupId': ConvertLong(obj.PreConditionGroupId(), password),
        'PreConditionFavorScheduleId': ConvertLong(obj.PreConditionFavorScheduleId(), password),
        'FavorScheduleId': ConvertLong(obj.FavorScheduleId(), password),
        'NextGroupId': ConvertLong(obj.NextGroupId(), password),
        'FeedbackTimeMillisec': ConvertLong(obj.FeedbackTimeMillisec(), password),
        'MessageType': AcademyMessageTypes(ConvertInt(obj.MessageType(), password)).name,
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'MessageKR': ConvertString(obj.MessageKR(), password),
        'MessageJP': ConvertString(obj.MessageJP(), password),
        'MessageTH': ConvertString(obj.MessageTH(), password),
        'MessageTW': ConvertString(obj.MessageTW(), password),
        'MessageEN': ConvertString(obj.MessageEN(), password),
        'MessageDE': ConvertString(obj.MessageDE(), password),
        'MessageFR': ConvertString(obj.MessageFR(), password),
    }

def dump_AcademyMessanger3Excel(obj, password) -> dict:
    return {
        'MessageGroupId': ConvertLong(obj.MessageGroupId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MessageCondition': AcademyMessageConditions(ConvertInt(obj.MessageCondition(), password)).name,
        'ConditionValue': ConvertLong(obj.ConditionValue(), password),
        'PreConditionGroupId': ConvertLong(obj.PreConditionGroupId(), password),
        'PreConditionFavorScheduleId': ConvertLong(obj.PreConditionFavorScheduleId(), password),
        'FavorScheduleId': ConvertLong(obj.FavorScheduleId(), password),
        'NextGroupId': ConvertLong(obj.NextGroupId(), password),
        'FeedbackTimeMillisec': ConvertLong(obj.FeedbackTimeMillisec(), password),
        'MessageType': AcademyMessageTypes(ConvertInt(obj.MessageType(), password)).name,
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'MessageKR': ConvertString(obj.MessageKR(), password),
        'MessageJP': ConvertString(obj.MessageJP(), password),
        'MessageTH': ConvertString(obj.MessageTH(), password),
        'MessageTW': ConvertString(obj.MessageTW(), password),
        'MessageEN': ConvertString(obj.MessageEN(), password),
        'MessageDE': ConvertString(obj.MessageDE(), password),
        'MessageFR': ConvertString(obj.MessageFR(), password),
    }

def dump_AcademyMessangerExcel(obj, password) -> dict:
    return {
        'MessageGroupId': ConvertLong(obj.MessageGroupId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MessageCondition': AcademyMessageConditions(ConvertInt(obj.MessageCondition(), password)).name,
        'ConditionValue': ConvertLong(obj.ConditionValue(), password),
        'PreConditionGroupId': ConvertLong(obj.PreConditionGroupId(), password),
        'PreConditionFavorScheduleId': ConvertLong(obj.PreConditionFavorScheduleId(), password),
        'FavorScheduleId': ConvertLong(obj.FavorScheduleId(), password),
        'NextGroupId': ConvertLong(obj.NextGroupId(), password),
        'FeedbackTimeMillisec': ConvertLong(obj.FeedbackTimeMillisec(), password),
        'MessageType': AcademyMessageTypes(ConvertInt(obj.MessageType(), password)).name,
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'MessageKR': ConvertString(obj.MessageKR(), password),
        'MessageJP': ConvertString(obj.MessageJP(), password),
        'MessageTH': ConvertString(obj.MessageTH(), password),
        'MessageTW': ConvertString(obj.MessageTW(), password),
        'MessageEN': ConvertString(obj.MessageEN(), password),
        'MessageDE': ConvertString(obj.MessageDE(), password),
        'MessageFR': ConvertString(obj.MessageFR(), password),
    }

def dump_AcademyRewardExcel(obj, password) -> dict:
    return {
        'Location': ConvertString(obj.Location(), password),
        'ScheduleGroupId': ConvertLong(obj.ScheduleGroupId(), password),
        'OrderInGroup': ConvertLong(obj.OrderInGroup(), password),
        'Id': ConvertLong(obj.Id(), password),
        'ProgressTexture': ConvertString(obj.ProgressTexture(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'LocationRank': ConvertLong(obj.LocationRank(), password),
        'FavorExp': ConvertLong(obj.FavorExp(), password),
        'SecretStoneAmount': ConvertLong(obj.SecretStoneAmount(), password),
        'SecretStoneProb': ConvertLong(obj.SecretStoneProb(), password),
        'ExtraFavorExp': ConvertLong(obj.ExtraFavorExp(), password),
        'ExtraFavorExpProb': ConvertLong(obj.ExtraFavorExpProb(), password),
        'ExtraRewardParcelType': [ParcelType(ConvertInt(obj.ExtraRewardParcelType(j), password)).name for j in range(obj.ExtraRewardParcelTypeLength())],
        'ExtraRewardParcelId': [ConvertLong(obj.ExtraRewardParcelId(j), password) for j in range(obj.ExtraRewardParcelIdLength())],
        'ExtraRewardAmount': [ConvertLong(obj.ExtraRewardAmount(j), password) for j in range(obj.ExtraRewardAmountLength())],
        'ExtraRewardProb': [ConvertLong(obj.ExtraRewardProb(j), password) for j in range(obj.ExtraRewardProbLength())],
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardAmount': [ConvertLong(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_AcademyTicketExcel(obj, password) -> dict:
    return {
        'LocationRankSum': ConvertLong(obj.LocationRankSum(), password),
        'ScheduleTicktetMax': ConvertLong(obj.ScheduleTicktetMax(), password),
    }

def dump_AcademyZoneExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocationId': ConvertLong(obj.LocationId(), password),
        'LocationRankForUnlock': ConvertLong(obj.LocationRankForUnlock(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'StudentVisitProb': [ConvertLong(obj.StudentVisitProb(j), password) for j in range(obj.StudentVisitProbLength())],
        'RewardGroupId': [ConvertLong(obj.RewardGroupId(j), password) for j in range(obj.RewardGroupIdLength())],
        'Tags': [Tag(ConvertInt(obj.Tags(j), password)).name for j in range(obj.TagsLength())],
    }

def dump_AccountLevelExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Level': ConvertLong(obj.Level(), password),
        'Exp': ConvertLong(obj.Exp(), password),
        'APAutoChargeMax': ConvertLong(obj.APAutoChargeMax(), password),
    }

def dump_AddressableBlackListExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'FolderPath': [ConvertString(obj.FolderPath(j), password) for j in range(obj.FolderPathLength())],
        'ResourcePath': [ConvertString(obj.ResourcePath(j), password) for j in range(obj.ResourcePathLength())],
    }

def dump_AddressableWhiteListExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'FolderPath': [ConvertString(obj.FolderPath(j), password) for j in range(obj.FolderPathLength())],
        'ResourcePath': [ConvertString(obj.ResourcePath(j), password) for j in range(obj.ResourcePathLength())],
    }

def dump_BlendData(obj, password) -> dict:
    return {
        'Type': ConvertInt(obj.Type(), password),
        'InfoList': [dump_BlendInfo(obj.InfoList(j), password) for j in range(obj.InfoListLength())],
    }

def dump_BlendInfo(obj, password) -> dict:
    return {
        'From': ConvertInt(obj.From(), password),
        'To': ConvertInt(obj.To(), password),
        'Blend': ConvertFloat(obj.Blend(), password),
    }

def dump_AnimatorData(obj, password) -> dict:
    return {
        'DefaultStateName': ConvertString(obj.DefaultStateName(), password),
        'Name': ConvertString(obj.Name(), password),
        'DataList': [dump_AniStateData(obj.DataList(j), password) for j in range(obj.DataListLength())],
    }

def dump_AniStateData(obj, password) -> dict:
    return {
        'StateName': ConvertString(obj.StateName(), password),
        'StatePrefix': ConvertString(obj.StatePrefix(), password),
        'StateNameWithPrefix': ConvertString(obj.StateNameWithPrefix(), password),
        'Tag': ConvertString(obj.Tag(), password),
        'SpeedParameterName': ConvertString(obj.SpeedParameterName(), password),
        'SpeedParamter': ConvertFloat(obj.SpeedParamter(), password),
        'StateSpeed': ConvertFloat(obj.StateSpeed(), password),
        'ClipName': ConvertString(obj.ClipName(), password),
        'Length': ConvertFloat(obj.Length(), password),
        'FrameRate': ConvertFloat(obj.FrameRate(), password),
        'IsLooping': obj.IsLooping(),
        'Events': [dump_AniEventData(obj.Events(j), password) for j in range(obj.EventsLength())],
    }

def dump_AniEventData(obj, password) -> dict:
    return {
        'Name': ConvertString(obj.Name(), password),
        'Time': ConvertFloat(obj.Time(), password),
        'IntParam': ConvertInt(obj.IntParam(), password),
        'FloatParam': ConvertFloat(obj.FloatParam(), password),
        'StringParam': ConvertString(obj.StringParam(), password),
    }

def dump_ArenaMapExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'TerrainType': ConvertLong(obj.TerrainType(), password),
        'TerrainTypeLocalizeKey': ConvertString(obj.TerrainTypeLocalizeKey(), password),
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'GroundGroupId': ConvertLong(obj.GroundGroupId(), password),
        'GroundGroupNameLocalizeKey': ConvertString(obj.GroundGroupNameLocalizeKey(), password),
        'StartRank': ConvertLong(obj.StartRank(), password),
        'EndRank': ConvertLong(obj.EndRank(), password),
        'GroundId': ConvertLong(obj.GroundId(), password),
    }

def dump_ArenaNPCExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'Rank': ConvertLong(obj.Rank(), password),
        'NPCAccountLevel': ConvertLong(obj.NPCAccountLevel(), password),
        'NPCLevel': ConvertLong(obj.NPCLevel(), password),
        'NPCLevelDeviation': ConvertLong(obj.NPCLevelDeviation(), password),
        'NPCStarGrade': ConvertLong(obj.NPCStarGrade(), password),
        'UseTSS': obj.UseTSS(),
        'ExceptionCharacterRarities': [Rarity(ConvertInt(obj.ExceptionCharacterRarities(j), password)).name for j in range(obj.ExceptionCharacterRaritiesLength())],
        'ExceptionMainCharacterIds': [ConvertLong(obj.ExceptionMainCharacterIds(j), password) for j in range(obj.ExceptionMainCharacterIdsLength())],
        'ExceptionSupportCharacterIds': [ConvertLong(obj.ExceptionSupportCharacterIds(j), password) for j in range(obj.ExceptionSupportCharacterIdsLength())],
        'ExceptionTSSIds': [ConvertLong(obj.ExceptionTSSIds(j), password) for j in range(obj.ExceptionTSSIdsLength())],
    }

def dump_ArenaRewardExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'ArenaRewardType_': ArenaRewardType(ConvertInt(obj.ArenaRewardType_(), password)).name,
        'RankStart': ConvertLong(obj.RankStart(), password),
        'RankEnd': ConvertLong(obj.RankEnd(), password),
        'RankIconPath': ConvertString(obj.RankIconPath(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelUniqueId': [ConvertLong(obj.RewardParcelUniqueId(j), password) for j in range(obj.RewardParcelUniqueIdLength())],
        'RewardParcelUniqueName': [ConvertString(obj.RewardParcelUniqueName(j), password) for j in range(obj.RewardParcelUniqueNameLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_ArenaSeasonCloseRewardExcel(obj, password) -> dict:
    return {
        'SeasonId': ConvertLong(obj.SeasonId(), password),
        'RankStart': ConvertLong(obj.RankStart(), password),
        'RankEnd': ConvertLong(obj.RankEnd(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelUniqueId': [ConvertLong(obj.RewardParcelUniqueId(j), password) for j in range(obj.RewardParcelUniqueIdLength())],
        'RewardParcelUniqueName': [ConvertString(obj.RewardParcelUniqueName(j), password) for j in range(obj.RewardParcelUniqueNameLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_ArenaSeasonExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'SeasonStartDate': ConvertString(obj.SeasonStartDate(), password),
        'SeasonEndDate': ConvertString(obj.SeasonEndDate(), password),
        'SeasonGroupLimit': ConvertLong(obj.SeasonGroupLimit(), password),
        'PrevSeasonId': ConvertLong(obj.PrevSeasonId(), password),
    }

def dump_AttendanceExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Type': AttendanceType(ConvertInt(obj.Type(), password)).name,
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'AccountType': AccountState(ConvertInt(obj.AccountType(), password)).name,
        'AccountLevelLimit': ConvertLong(obj.AccountLevelLimit(), password),
        'Title': ConvertString(obj.Title(), password),
        'InfomationLocalizeCode': ConvertString(obj.InfomationLocalizeCode(), password),
        'CountRule': AttendanceCountRule(ConvertInt(obj.CountRule(), password)).name,
        'CountReset': AttendanceResetType(ConvertInt(obj.CountReset(), password)).name,
        'BookSize': ConvertLong(obj.BookSize(), password),
        'StartDate': ConvertString(obj.StartDate(), password),
        'StartableEndDate': ConvertString(obj.StartableEndDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'ExpiryDate': ConvertLong(obj.ExpiryDate(), password),
        'MailType_': MailType(ConvertInt(obj.MailType_(), password)).name,
        'DialogCategory_': DialogCategory(ConvertInt(obj.DialogCategory_(), password)).name,
        'TitleImagePath': ConvertString(obj.TitleImagePath(), password),
        'DecorationImagePath': ConvertString(obj.DecorationImagePath(), password),
    }

def dump_AttendanceRewardExcel(obj, password) -> dict:
    return {
        'AttendanceId': ConvertLong(obj.AttendanceId(), password),
        'Day': ConvertLong(obj.Day(), password),
        'RewardIcon': ConvertString(obj.RewardIcon(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardId': [ConvertLong(obj.RewardId(j), password) for j in range(obj.RewardIdLength())],
        'RewardAmount': [ConvertLong(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_AudioAnimatorExcel(obj, password) -> dict:
    return {
        'ControllerNameHash': ConvertUInt(obj.ControllerNameHash(), password),
        'VoiceNamePrefix': ConvertString(obj.VoiceNamePrefix(), password),
        'StateNameHash': ConvertUInt(obj.StateNameHash(), password),
        'StateName': ConvertString(obj.StateName(), password),
        'IgnoreInterruptDelay': obj.IgnoreInterruptDelay(),
        'IgnoreInterruptPlay': obj.IgnoreInterruptPlay(),
        'Volume': ConvertFloat(obj.Volume(), password),
        'Delay': ConvertFloat(obj.Delay(), password),
        'AudioPriority': ConvertInt(obj.AudioPriority(), password),
        'AudioClipPath': [ConvertString(obj.AudioClipPath(j), password) for j in range(obj.AudioClipPathLength())],
        'VoiceHash': [ConvertUInt(obj.VoiceHash(j), password) for j in range(obj.VoiceHashLength())],
    }

def dump_BGMExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'Path': ConvertString(obj.Path(), password),
        'Volume': ConvertFloat(obj.Volume(), password),
        'LoopStartTime': ConvertFloat(obj.LoopStartTime(), password),
        'LoopEndTime': ConvertFloat(obj.LoopEndTime(), password),
        'LoopTranstionTime': ConvertFloat(obj.LoopTranstionTime(), password),
        'LoopOffsetTime': ConvertFloat(obj.LoopOffsetTime(), password),
    }

def dump_BGMRaidExcel(obj, password) -> dict:
    return {
        'StageId': ConvertLong(obj.StageId(), password),
        'PhaseIndex': ConvertLong(obj.PhaseIndex(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
    }

def dump_BGMUIExcel(obj, password) -> dict:
    return {
        'UIPrefab': ConvertUInt(obj.UIPrefab(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
    }

def dump_BGM_GlobalExcel(obj, password) -> dict:
    return {
        'GroupBGMId': ConvertLong(obj.GroupBGMId(), password),
        'BGMIdKr': ConvertLong(obj.BGMIdKr(), password),
        'BGMIdJp': ConvertLong(obj.BGMIdJp(), password),
        'BGMIdTh': ConvertLong(obj.BGMIdTh(), password),
        'BGMIdTw': ConvertLong(obj.BGMIdTw(), password),
        'BGMIdEn': ConvertLong(obj.BGMIdEn(), password),
        'BGMIdDe': ConvertLong(obj.BGMIdDe(), password),
        'BGMIdFr': ConvertLong(obj.BGMIdFr(), password),
    }

def dump_BattleLevelFactorExcel(obj, password) -> dict:
    return {
        'LevelDiff': ConvertInt(obj.LevelDiff(), password),
        'DamageRate': ConvertLong(obj.DamageRate(), password),
    }

def dump_BossExternalBTExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'AIPhase': ConvertLong(obj.AIPhase(), password),
        'ExternalBTNodeType_': ExternalBTNodeType(ConvertInt(obj.ExternalBTNodeType_(), password)).name,
        'ExternalBTTrigger_': ExternalBTTrigger(ConvertInt(obj.ExternalBTTrigger_(), password)).name,
        'TriggerArgument': ConvertString(obj.TriggerArgument(), password),
        'BehaviorRate': ConvertLong(obj.BehaviorRate(), password),
        'ExternalBehavior_': ExternalBehavior(ConvertInt(obj.ExternalBehavior_(), password)).name,
        'BehaviorArgument': ConvertString(obj.BehaviorArgument(), password),
    }

def dump_BossPhaseExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'AIPhase': ConvertLong(obj.AIPhase(), password),
        'NormalAttackSkillUniqueName': ConvertString(obj.NormalAttackSkillUniqueName(), password),
        'UseExSkill': [obj.UseExSkill(j) for j in range(obj.UseExSkillLength())],
    }

def dump_BuffParticleExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'UniqueName': ConvertString(obj.UniqueName(), password),
        'BuffType': ConvertString(obj.BuffType(), password),
        'BuffName': ConvertString(obj.BuffName(), password),
        'ResourcePath': ConvertString(obj.ResourcePath(), password),
    }

def dump_BulletArmorDamageFactorExcel(obj, password) -> dict:
    return {
        'DamageFactorGroupId': ConvertString(obj.DamageFactorGroupId(), password),
        'BulletType_': BulletType(ConvertInt(obj.BulletType_(), password)).name,
        'ArmorType_': ArmorType(ConvertInt(obj.ArmorType_(), password)).name,
        'DamageRate': ConvertLong(obj.DamageRate(), password),
        'DamageAttribute_': DamageAttribute(ConvertInt(obj.DamageAttribute_(), password)).name,
        'MinDamageRate': ConvertLong(obj.MinDamageRate(), password),
        'MaxDamageRate': ConvertLong(obj.MaxDamageRate(), password),
        'ShowHighlightFloater': obj.ShowHighlightFloater(),
    }

def dump_CafeInteractionExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'BubbleType_': [BubbleType(ConvertInt(obj.BubbleType_(j), password)).name for j in range(obj.BubbleType_Length())],
        'BubbleDuration': [ConvertLong(obj.BubbleDuration(j), password) for j in range(obj.BubbleDurationLength())],
        'FavorEmoticonRewardParcelType': ParcelType(ConvertInt(obj.FavorEmoticonRewardParcelType(), password)).name,
        'FavorEmoticonRewardId': ConvertLong(obj.FavorEmoticonRewardId(), password),
        'FavorEmoticonRewardAmount': ConvertLong(obj.FavorEmoticonRewardAmount(), password),
        'CafeCharacterState_': [CafeCharacterState(ConvertInt(obj.CafeCharacterState_(j), password)).name for j in range(obj.CafeCharacterState_Length())],
    }

def dump_CafeRankExcel(obj, password) -> dict:
    return {
        'Rank': ConvertLong(obj.Rank(), password),
        'RecipeId': ConvertLong(obj.RecipeId(), password),
        'ComfortMax': ConvertLong(obj.ComfortMax(), password),
        'ActionPointProductionCoefficient': ConvertLong(obj.ActionPointProductionCoefficient(), password),
        'ActionPointProductionCorrectionValue': ConvertLong(obj.ActionPointProductionCorrectionValue(), password),
        'ActionPointStorageMax': ConvertLong(obj.ActionPointStorageMax(), password),
        'GoldProductionCoefficient': ConvertLong(obj.GoldProductionCoefficient(), password),
        'GoldProductionCorrectionValue': ConvertLong(obj.GoldProductionCorrectionValue(), password),
        'GoldStorageMax': ConvertLong(obj.GoldStorageMax(), password),
        'TagCountMax': ConvertLong(obj.TagCountMax(), password),
        'CharacterVisitMin': ConvertInt(obj.CharacterVisitMin(), password),
        'CharacterVisitMax': ConvertInt(obj.CharacterVisitMax(), password),
    }

def dump_CameraExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'MinDistance': ConvertFloat(obj.MinDistance(), password),
        'MaxDistance': ConvertFloat(obj.MaxDistance(), password),
        'RotationX': ConvertFloat(obj.RotationX(), password),
        'RotationY': ConvertFloat(obj.RotationY(), password),
        'MoveInstantly': obj.MoveInstantly(),
        'LeftMargin': ConvertFloat(obj.LeftMargin(), password),
        'BottomMargin': ConvertFloat(obj.BottomMargin(), password),
        'IgnoreEnemies': obj.IgnoreEnemies(),
        'UseRailPointCompensation': obj.UseRailPointCompensation(),
    }

def dump_CampaignChapterExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Name': ConvertString(obj.Name(), password),
        'NormalImagePath': ConvertString(obj.NormalImagePath(), password),
        'HardImagePath': ConvertString(obj.HardImagePath(), password),
        'Order': ConvertLong(obj.Order(), password),
        'PreChapterId': [ConvertLong(obj.PreChapterId(j), password) for j in range(obj.PreChapterIdLength())],
        'ChapterRewardId': ConvertLong(obj.ChapterRewardId(), password),
        'ChapterHardRewardId': ConvertLong(obj.ChapterHardRewardId(), password),
        'ChapterVeryHardRewardId': ConvertLong(obj.ChapterVeryHardRewardId(), password),
        'NormalCampaignStageId': [ConvertLong(obj.NormalCampaignStageId(j), password) for j in range(obj.NormalCampaignStageIdLength())],
        'HardCampaignStageId': [ConvertLong(obj.HardCampaignStageId(j), password) for j in range(obj.HardCampaignStageIdLength())],
        'VeryHardCampaignStageId': [ConvertLong(obj.VeryHardCampaignStageId(j), password) for j in range(obj.VeryHardCampaignStageIdLength())],
    }

def dump_CampaignChapterRewardExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ChapterRewardParcelType': [ParcelType(ConvertInt(obj.ChapterRewardParcelType(j), password)).name for j in range(obj.ChapterRewardParcelTypeLength())],
        'ChapterRewardId': [ConvertLong(obj.ChapterRewardId(j), password) for j in range(obj.ChapterRewardIdLength())],
        'ChapterRewardAmount': [ConvertInt(obj.ChapterRewardAmount(j), password) for j in range(obj.ChapterRewardAmountLength())],
    }

def dump_CampaignStageExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Name': ConvertString(obj.Name(), password),
        'StageNumber': ConvertInt(obj.StageNumber(), password),
        'CleardScenarioId': ConvertLong(obj.CleardScenarioId(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'StageEnterCostType': CurrencyTypes(ConvertInt(obj.StageEnterCostType(), password)).name,
        'StageEnterCostAmount': ConvertInt(obj.StageEnterCostAmount(), password),
        'StageEnterEchelonCount': ConvertInt(obj.StageEnterEchelonCount(), password),
        'StarConditionTacticRankSCount': ConvertLong(obj.StarConditionTacticRankSCount(), password),
        'StarConditionTurnCount': ConvertLong(obj.StarConditionTurnCount(), password),
        'EnterScenarioGroupId': [ConvertLong(obj.EnterScenarioGroupId(j), password) for j in range(obj.EnterScenarioGroupIdLength())],
        'ClearScenarioGroupId': [ConvertLong(obj.ClearScenarioGroupId(j), password) for j in range(obj.ClearScenarioGroupIdLength())],
        'StrategyMap': ConvertString(obj.StrategyMap(), password),
        'StrategyMapBG': ConvertString(obj.StrategyMapBG(), password),
        'CampaignStageRewardId': ConvertLong(obj.CampaignStageRewardId(), password),
        'MaxTurn': ConvertInt(obj.MaxTurn(), password),
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'RecommandLevel': ConvertInt(obj.RecommandLevel(), password),
        'BgmId': ConvertString(obj.BgmId(), password),
        'StrategyEnvironment_': StrategyEnvironment(ConvertInt(obj.StrategyEnvironment_(), password)).name,
        'GroundId': ConvertLong(obj.GroundId(), password),
        'ContentType_': ContentType(ConvertInt(obj.ContentType_(), password)).name,
        'BGMId': ConvertLong(obj.BGMId(), password),
        'FirstClearReportEventName': ConvertString(obj.FirstClearReportEventName(), password),
        'FirstClearFunnelMessage': ConvertString(obj.FirstClearFunnelMessage(), password),
        'FirstClearEventMessage': ConvertString(obj.FirstClearEventMessage(), password),
        'TacticRewardExp': ConvertLong(obj.TacticRewardExp(), password),
        'FixedEchelonId': ConvertLong(obj.FixedEchelonId(), password),
    }

def dump_CampaignStageRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'RewardTag_': RewardTag(ConvertInt(obj.RewardTag_(), password)).name,
        'StageRewardProb': ConvertInt(obj.StageRewardProb(), password),
        'StageRewardParcelType': ParcelType(ConvertInt(obj.StageRewardParcelType(), password)).name,
        'StageRewardId': ConvertLong(obj.StageRewardId(), password),
        'StageRewardAmount': ConvertInt(obj.StageRewardAmount(), password),
        'IsDisplayed': obj.IsDisplayed(),
    }

def dump_CampaignStrategyObjectExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Key': ConvertUInt(obj.Key(), password),
        'Name': ConvertString(obj.Name(), password),
        'PrefabName': ConvertString(obj.PrefabName(), password),
        'StrategyObjectType_': StrategyObjectType(ConvertInt(obj.StrategyObjectType_(), password)).name,
        'StrategyRewardParcelType': ParcelType(ConvertInt(obj.StrategyRewardParcelType(), password)).name,
        'StrategyRewardID': ConvertLong(obj.StrategyRewardID(), password),
        'StrategyRewardName': ConvertString(obj.StrategyRewardName(), password),
        'StrategyRewardAmount': ConvertInt(obj.StrategyRewardAmount(), password),
        'StrategySightRange': ConvertLong(obj.StrategySightRange(), password),
        'PortalId': ConvertInt(obj.PortalId(), password),
        'HealValue': ConvertInt(obj.HealValue(), password),
        'SwithId': ConvertInt(obj.SwithId(), password),
        'BuffId': ConvertInt(obj.BuffId(), password),
        'Disposable': obj.Disposable(),
    }

def dump_CampaignUnitExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Key': ConvertUInt(obj.Key(), password),
        'Name': ConvertString(obj.Name(), password),
        'PrefabName': ConvertString(obj.PrefabName(), password),
        'GroundId': ConvertLong(obj.GroundId(), password),
        'IsBoss': obj.IsBoss(),
        'MoveRange': ConvertInt(obj.MoveRange(), password),
        'AIMoveType': StrategyAIType(ConvertInt(obj.AIMoveType(), password)).name,
        'Grade': HexaUnitGrade(ConvertInt(obj.Grade(), password)).name,
        'EnvironmentType': TacticEnvironment(ConvertInt(obj.EnvironmentType(), password)).name,
        'Scale': ConvertFloat(obj.Scale(), password),
    }

def dump_CharacterAIExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EngageType_': EngageType(ConvertInt(obj.EngageType_(), password)).name,
        'Positioning': PositioningType(ConvertInt(obj.Positioning(), password)).name,
        'DistanceReduceRatioObstaclePath': ConvertLong(obj.DistanceReduceRatioObstaclePath(), password),
        'DistanceReduceObstaclePath': ConvertLong(obj.DistanceReduceObstaclePath(), password),
        'DistanceReduceRatioFormationPath': ConvertLong(obj.DistanceReduceRatioFormationPath(), password),
        'DistanceReduceFormationPath': ConvertLong(obj.DistanceReduceFormationPath(), password),
        'MinimumPositionGap': ConvertLong(obj.MinimumPositionGap(), password),
        'CanUseObstacleOfKneelMotion': obj.CanUseObstacleOfKneelMotion(),
        'CanUseObstacleOfStandMotion': obj.CanUseObstacleOfStandMotion(),
        'HasTargetSwitchingMotion': obj.HasTargetSwitchingMotion(),
    }

def dump_CharacterAcademyTagsExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'FavorTags': [Tag(ConvertInt(obj.FavorTags(j), password)).name for j in range(obj.FavorTagsLength())],
        'FavorItemTags': [Tag(ConvertInt(obj.FavorItemTags(j), password)).name for j in range(obj.FavorItemTagsLength())],
        'ForbiddenTags': [Tag(ConvertInt(obj.ForbiddenTags(j), password)).name for j in range(obj.ForbiddenTagsLength())],
    }

def dump_CharacterCombatSkinExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertString(obj.GroupId(), password),
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'ResourcePath': ConvertString(obj.ResourcePath(), password),
    }

def dump_CharacterDialogEventExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'EventID': ConvertLong(obj.EventID(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'DialogCategory_': DialogCategory(ConvertInt(obj.DialogCategory_(), password)).name,
        'DialogCondition_': DialogCondition(ConvertInt(obj.DialogCondition_(), password)).name,
        'DialogConditionDetail_': DialogConditionDetail(ConvertInt(obj.DialogConditionDetail_(), password)).name,
        'DialogConditionDetailValue': ConvertLong(obj.DialogConditionDetailValue(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'DialogType_': DialogType(ConvertInt(obj.DialogType_(), password)).name,
        'ActionName': ConvertString(obj.ActionName(), password),
        'Duration': ConvertLong(obj.Duration(), password),
        'AnimationName': ConvertString(obj.AnimationName(), password),
        'LocalizeKR': ConvertString(obj.LocalizeKR(), password),
        'LocalizeJP': ConvertString(obj.LocalizeJP(), password),
        'LocalizeTH': ConvertString(obj.LocalizeTH(), password),
        'LocalizeTW': ConvertString(obj.LocalizeTW(), password),
        'LocalizeEN': ConvertString(obj.LocalizeEN(), password),
        'LocalizeDE': ConvertString(obj.LocalizeDE(), password),
        'LocalizeFR': ConvertString(obj.LocalizeFR(), password),
        'VoiceClipsKr': [ConvertString(obj.VoiceClipsKr(j), password) for j in range(obj.VoiceClipsKrLength())],
        'VoiceClipsJp': [ConvertString(obj.VoiceClipsJp(j), password) for j in range(obj.VoiceClipsJpLength())],
        'VoiceClipsTh': [ConvertString(obj.VoiceClipsTh(j), password) for j in range(obj.VoiceClipsThLength())],
        'VoiceClipsTw': [ConvertString(obj.VoiceClipsTw(j), password) for j in range(obj.VoiceClipsTwLength())],
        'VoiceClipsEn': [ConvertString(obj.VoiceClipsEn(j), password) for j in range(obj.VoiceClipsEnLength())],
        'VoiceClipsDe': [ConvertString(obj.VoiceClipsDe(j), password) for j in range(obj.VoiceClipsDeLength())],
        'VoiceClipsFr': [ConvertString(obj.VoiceClipsFr(j), password) for j in range(obj.VoiceClipsFrLength())],
    }

def dump_CharacterDialogExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'DialogCategory_': DialogCategory(ConvertInt(obj.DialogCategory_(), password)).name,
        'DialogCondition_': DialogCondition(ConvertInt(obj.DialogCondition_(), password)).name,
        'Anniversary_': Anniversary(ConvertInt(obj.Anniversary_(), password)).name,
        'StartDate': ConvertString(obj.StartDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'DialogType_': DialogType(ConvertInt(obj.DialogType_(), password)).name,
        'ActionName': ConvertString(obj.ActionName(), password),
        'Duration': ConvertLong(obj.Duration(), password),
        'AnimationName': ConvertString(obj.AnimationName(), password),
        'LocalizeKR': ConvertString(obj.LocalizeKR(), password),
        'LocalizeJP': ConvertString(obj.LocalizeJP(), password),
        'LocalizeTH': ConvertString(obj.LocalizeTH(), password),
        'LocalizeTW': ConvertString(obj.LocalizeTW(), password),
        'LocalizeEN': ConvertString(obj.LocalizeEN(), password),
        'LocalizeDE': ConvertString(obj.LocalizeDE(), password),
        'LocalizeFR': ConvertString(obj.LocalizeFR(), password),
        'VoiceClipsKr': [ConvertString(obj.VoiceClipsKr(j), password) for j in range(obj.VoiceClipsKrLength())],
        'VoiceClipsJp': [ConvertString(obj.VoiceClipsJp(j), password) for j in range(obj.VoiceClipsJpLength())],
        'VoiceClipsTh': [ConvertString(obj.VoiceClipsTh(j), password) for j in range(obj.VoiceClipsThLength())],
        'VoiceClipsTw': [ConvertString(obj.VoiceClipsTw(j), password) for j in range(obj.VoiceClipsTwLength())],
        'VoiceClipsEn': [ConvertString(obj.VoiceClipsEn(j), password) for j in range(obj.VoiceClipsEnLength())],
        'VoiceClipsDe': [ConvertString(obj.VoiceClipsDe(j), password) for j in range(obj.VoiceClipsDeLength())],
        'VoiceClipsFr': [ConvertString(obj.VoiceClipsFr(j), password) for j in range(obj.VoiceClipsFrLength())],
    }

def dump_CharacterExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'CollectionVisible': obj.CollectionVisible(),
        'IsPlayableCharacter': obj.IsPlayableCharacter(),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'TacticEntityType_': TacticEntityType(ConvertInt(obj.TacticEntityType_(), password)).name,
        'CanSurvive': obj.CanSurvive(),
        'IsDummy': obj.IsDummy(),
        'SubPartsCount': ConvertInt(obj.SubPartsCount(), password),
        'TacticRole_': TacticRole(ConvertInt(obj.TacticRole_(), password)).name,
        'WeaponType_': WeaponType(ConvertInt(obj.WeaponType_(), password)).name,
        'TacticRange_': TacticRange(ConvertInt(obj.TacticRange_(), password)).name,
        'BulletType_': BulletType(ConvertInt(obj.BulletType_(), password)).name,
        'ArmorType_': ArmorType(ConvertInt(obj.ArmorType_(), password)).name,
        'AimIKType_': AimIKType(ConvertInt(obj.AimIKType_(), password)).name,
        'School_': School(ConvertInt(obj.School_(), password)).name,
        'Club_': Club(ConvertInt(obj.Club_(), password)).name,
        'DefaultStarGrade': ConvertInt(obj.DefaultStarGrade(), password),
        'MaxStarGrade': ConvertInt(obj.MaxStarGrade(), password),
        'StatLevelUpType_': StatLevelUpType(ConvertInt(obj.StatLevelUpType_(), password)).name,
        'SquadType_': SquadType(ConvertInt(obj.SquadType_(), password)).name,
        'Jumpable': obj.Jumpable(),
        'PersonalityId': ConvertLong(obj.PersonalityId(), password),
        'CharacterAIId': ConvertLong(obj.CharacterAIId(), password),
        'ScenarioCharacter': ConvertString(obj.ScenarioCharacter(), password),
        'SpawnTemplateId': ConvertUInt(obj.SpawnTemplateId(), password),
        'FavorLevelupType': ConvertInt(obj.FavorLevelupType(), password),
        'EquipmentSlot': [EquipmentCategory(ConvertInt(obj.EquipmentSlot(j), password)).name for j in range(obj.EquipmentSlotLength())],
        'SpineResourceName': ConvertString(obj.SpineResourceName(), password),
        'SpineResourceNameDiorama': ConvertString(obj.SpineResourceNameDiorama(), password),
        'EntityMaterialType_': EntityMaterialType(ConvertInt(obj.EntityMaterialType_(), password)).name,
        'ModelPrefabName': ConvertString(obj.ModelPrefabName(), password),
        'TextureDir': ConvertString(obj.TextureDir(), password),
        'TextureEchelon': ConvertString(obj.TextureEchelon(), password),
        'CollectionTexturePath': ConvertString(obj.CollectionTexturePath(), password),
        'CollectionBGTexturePath': ConvertString(obj.CollectionBGTexturePath(), password),
        'TextureBoss': ConvertString(obj.TextureBoss(), password),
        'TextureSkillCard': [ConvertString(obj.TextureSkillCard(j), password) for j in range(obj.TextureSkillCardLength())],
        'WeaponImagePath': ConvertString(obj.WeaponImagePath(), password),
        'WeaponLocalizeId': ConvertUInt(obj.WeaponLocalizeId(), password),
        'DisplayEnemyInfo': obj.DisplayEnemyInfo(),
        'BodyRadius': ConvertLong(obj.BodyRadius(), password),
        'RandomEffectRadius': ConvertLong(obj.RandomEffectRadius(), password),
        'HpBarHeight': ConvertFloat(obj.HpBarHeight(), password),
        'HighlightFloaterHeight': ConvertFloat(obj.HighlightFloaterHeight(), password),
        'MoveStartFrame': ConvertInt(obj.MoveStartFrame(), password),
        'MoveEndFrame': ConvertInt(obj.MoveEndFrame(), password),
        'JumpMotionFrame': ConvertInt(obj.JumpMotionFrame(), password),
        'AppearFrame': ConvertInt(obj.AppearFrame(), password),
        'CanMove': obj.CanMove(),
        'CanFix': obj.CanFix(),
        'CanCrowdControl': obj.CanCrowdControl(),
        'CanBattleItemMove': obj.CanBattleItemMove(),
        'IsAirUnit': obj.IsAirUnit(),
        'AirUnitHeight': ConvertLong(obj.AirUnitHeight(), password),
        'Tags': [Tag(ConvertInt(obj.Tags(j), password)).name for j in range(obj.TagsLength())],
        'SecretStoneItemId': ConvertLong(obj.SecretStoneItemId(), password),
        'SecretStoneItemAmount': ConvertInt(obj.SecretStoneItemAmount(), password),
        'CharacterPieceItemId': ConvertLong(obj.CharacterPieceItemId(), password),
        'CharacterPieceItemAmount': ConvertInt(obj.CharacterPieceItemAmount(), password),
        'CombineRecipeId': ConvertLong(obj.CombineRecipeId(), password),
        'InformationPacel': ConvertString(obj.InformationPacel(), password),
        'AnimationSSR': ConvertString(obj.AnimationSSR(), password),
    }

def dump_CharacterIllustCoordinateExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'CharacterBodyCenterX': ConvertFloat(obj.CharacterBodyCenterX(), password),
        'CharacterBodyCenterY': ConvertFloat(obj.CharacterBodyCenterY(), password),
        'DefaultScale': ConvertFloat(obj.DefaultScale(), password),
        'MinScale': ConvertFloat(obj.MinScale(), password),
        'MaxScale': ConvertFloat(obj.MaxScale(), password),
    }

def dump_CharacterLevelExcel(obj, password) -> dict:
    return {
        'Level': ConvertInt(obj.Level(), password),
        'Exp': ConvertLong(obj.Exp(), password),
        'TotalExp': ConvertLong(obj.TotalExp(), password),
    }

def dump_CharacterLevelStatFactorExcel(obj, password) -> dict:
    return {
        'Level': ConvertLong(obj.Level(), password),
        'CriticalFactor': ConvertLong(obj.CriticalFactor(), password),
        'StabilityFactor': ConvertLong(obj.StabilityFactor(), password),
        'DefenceFactor': ConvertLong(obj.DefenceFactor(), password),
        'AccuracyFactor': ConvertLong(obj.AccuracyFactor(), password),
    }

def dump_CharacterSkillListExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MinimumGradeCharacterWeapon': ConvertInt(obj.MinimumGradeCharacterWeapon(), password),
        'IsFormConversion': obj.IsFormConversion(),
        'IsRootMotion': obj.IsRootMotion(),
        'IsMoveLeftRight': obj.IsMoveLeftRight(),
        'UseRandomAnimation': obj.UseRandomAnimation(),
        'NormalSkillGroupId': [ConvertString(obj.NormalSkillGroupId(j), password) for j in range(obj.NormalSkillGroupIdLength())],
        'ExSkillGroupId': [ConvertString(obj.ExSkillGroupId(j), password) for j in range(obj.ExSkillGroupIdLength())],
        'PublicSkillGroupId': [ConvertString(obj.PublicSkillGroupId(j), password) for j in range(obj.PublicSkillGroupIdLength())],
        'PassiveSkillGroupId': [ConvertString(obj.PassiveSkillGroupId(j), password) for j in range(obj.PassiveSkillGroupIdLength())],
        'LeaderSkillGroupId': [ConvertString(obj.LeaderSkillGroupId(j), password) for j in range(obj.LeaderSkillGroupIdLength())],
        'ExtraPassiveSkillGroupId': [ConvertString(obj.ExtraPassiveSkillGroupId(j), password) for j in range(obj.ExtraPassiveSkillGroupIdLength())],
    }

def dump_CharacterStatExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'StabilityRate': ConvertLong(obj.StabilityRate(), password),
        'StabilityPoint': ConvertLong(obj.StabilityPoint(), password),
        'AttackPower1': ConvertLong(obj.AttackPower1(), password),
        'AttackPower100': ConvertLong(obj.AttackPower100(), password),
        'MaxHP1': ConvertLong(obj.MaxHP1(), password),
        'MaxHP100': ConvertLong(obj.MaxHP100(), password),
        'DefensePower1': ConvertLong(obj.DefensePower1(), password),
        'DefensePower100': ConvertLong(obj.DefensePower100(), password),
        'HealPower1': ConvertLong(obj.HealPower1(), password),
        'HealPower100': ConvertLong(obj.HealPower100(), password),
        'DodgePoint': ConvertLong(obj.DodgePoint(), password),
        'AccuracyPoint': ConvertLong(obj.AccuracyPoint(), password),
        'CriticalPoint': ConvertLong(obj.CriticalPoint(), password),
        'CriticalResistPoint': ConvertLong(obj.CriticalResistPoint(), password),
        'CriticalDamageRate': ConvertLong(obj.CriticalDamageRate(), password),
        'CriticalDamageResistRate': ConvertLong(obj.CriticalDamageResistRate(), password),
        'BlockRate': ConvertLong(obj.BlockRate(), password),
        'HealEffectivenessRate': ConvertLong(obj.HealEffectivenessRate(), password),
        'OppressionPower': ConvertLong(obj.OppressionPower(), password),
        'OppressionResist': ConvertLong(obj.OppressionResist(), password),
        'DefensePenetration1': ConvertLong(obj.DefensePenetration1(), password),
        'DefensePenetration100': ConvertLong(obj.DefensePenetration100(), password),
        'AmmoCount': ConvertLong(obj.AmmoCount(), password),
        'AmmoCost': ConvertLong(obj.AmmoCost(), password),
        'IgnoreDelayCount': ConvertLong(obj.IgnoreDelayCount(), password),
        'NormalAttackSpeed': ConvertLong(obj.NormalAttackSpeed(), password),
        'Range': ConvertLong(obj.Range(), password),
        'InitialRangeRate': ConvertLong(obj.InitialRangeRate(), password),
        'MoveSpeed': ConvertLong(obj.MoveSpeed(), password),
        'SightPoint': ConvertLong(obj.SightPoint(), password),
        'ActiveGauge': ConvertLong(obj.ActiveGauge(), password),
        'GroggyGauge': ConvertInt(obj.GroggyGauge(), password),
        'GroggyTime': ConvertInt(obj.GroggyTime(), password),
        'StrategyMobility': ConvertLong(obj.StrategyMobility(), password),
        'ActionCount': ConvertLong(obj.ActionCount(), password),
        'StrategySightRange': ConvertLong(obj.StrategySightRange(), password),
        'DamageRatio': ConvertLong(obj.DamageRatio(), password),
        'DamagedRatio': ConvertLong(obj.DamagedRatio(), password),
        'StreetBattleAdaptation': TerrainAdaptationStat(ConvertInt(obj.StreetBattleAdaptation(), password)).name,
        'OutdoorBattleAdaptation': TerrainAdaptationStat(ConvertInt(obj.OutdoorBattleAdaptation(), password)).name,
        'IndoorBattleAdaptation': TerrainAdaptationStat(ConvertInt(obj.IndoorBattleAdaptation(), password)).name,
        'RegenCost': ConvertLong(obj.RegenCost(), password),
    }

def dump_CharacterStatLimitExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'TacticEntityType_': TacticEntityType(ConvertInt(obj.TacticEntityType_(), password)).name,
        'StatType_': StatType(ConvertInt(obj.StatType_(), password)).name,
        'StatMinValue': ConvertLong(obj.StatMinValue(), password),
        'StatMaxValue': ConvertLong(obj.StatMaxValue(), password),
        'StatRatioMinValue': ConvertLong(obj.StatRatioMinValue(), password),
        'StatRatioMaxValue': ConvertLong(obj.StatRatioMaxValue(), password),
    }

def dump_CharacterStatsDetailExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'DetailShowStats': [StatType(ConvertInt(obj.DetailShowStats(j), password)).name for j in range(obj.DetailShowStatsLength())],
        'IsStatsPercent': [obj.IsStatsPercent(j) for j in range(obj.IsStatsPercentLength())],
    }

def dump_CharacterStatsTransExcel(obj, password) -> dict:
    return {
        'TransSupportStats': StatType(ConvertInt(obj.TransSupportStats(), password)).name,
        'TransSupportStatsFactor': ConvertInt(obj.TransSupportStatsFactor(), password),
    }

def dump_CharacterTranscendenceExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'MaxFavorLevel': [ConvertInt(obj.MaxFavorLevel(j), password) for j in range(obj.MaxFavorLevelLength())],
        'StatBonusRateAttack': [ConvertLong(obj.StatBonusRateAttack(j), password) for j in range(obj.StatBonusRateAttackLength())],
        'StatBonusRateHP': [ConvertLong(obj.StatBonusRateHP(j), password) for j in range(obj.StatBonusRateHPLength())],
        'StatBonusRateHeal': [ConvertLong(obj.StatBonusRateHeal(j), password) for j in range(obj.StatBonusRateHealLength())],
        'RecipeId': [ConvertLong(obj.RecipeId(j), password) for j in range(obj.RecipeIdLength())],
        'SkillGroupIdA': [ConvertString(obj.SkillGroupIdA(j), password) for j in range(obj.SkillGroupIdALength())],
        'SkillGroupIdB': [ConvertString(obj.SkillGroupIdB(j), password) for j in range(obj.SkillGroupIdBLength())],
        'MaxlevelStar': [ConvertInt(obj.MaxlevelStar(j), password) for j in range(obj.MaxlevelStarLength())],
    }

def dump_CharacterWeaponExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ImagePath': ConvertString(obj.ImagePath(), password),
        'SetRecipe': ConvertLong(obj.SetRecipe(), password),
        'StatLevelUpType_': StatLevelUpType(ConvertInt(obj.StatLevelUpType_(), password)).name,
        'AttackPower': ConvertLong(obj.AttackPower(), password),
        'AttackPower100': ConvertLong(obj.AttackPower100(), password),
        'MaxHP': ConvertLong(obj.MaxHP(), password),
        'MaxHP100': ConvertLong(obj.MaxHP100(), password),
        'HealPower': ConvertLong(obj.HealPower(), password),
        'HealPower100': ConvertLong(obj.HealPower100(), password),
        'Unlock': [obj.Unlock(j) for j in range(obj.UnlockLength())],
        'RecipeId': [ConvertLong(obj.RecipeId(j), password) for j in range(obj.RecipeIdLength())],
        'MaxLevel': [ConvertInt(obj.MaxLevel(j), password) for j in range(obj.MaxLevelLength())],
        'PreviousSkillGroupId': [ConvertString(obj.PreviousSkillGroupId(j), password) for j in range(obj.PreviousSkillGroupIdLength())],
        'AfterSkillGroupId': [ConvertString(obj.AfterSkillGroupId(j), password) for j in range(obj.AfterSkillGroupIdLength())],
        'StatType': [EquipmentOptionType(ConvertInt(obj.StatType(j), password)).name for j in range(obj.StatTypeLength())],
        'StatValue': [ConvertLong(obj.StatValue(j), password) for j in range(obj.StatValueLength())],
    }

def dump_CharacterWeaponExpBonusExcel(obj, password) -> dict:
    return {
        'WeaponType_': WeaponType(ConvertInt(obj.WeaponType_(), password)).name,
        'WeaponExpGrowthA': ConvertInt(obj.WeaponExpGrowthA(), password),
        'WeaponExpGrowthB': ConvertInt(obj.WeaponExpGrowthB(), password),
        'WeaponExpGrowthC': ConvertInt(obj.WeaponExpGrowthC(), password),
        'WeaponExpGrowthZ': ConvertInt(obj.WeaponExpGrowthZ(), password),
    }

def dump_CharacterWeaponLevelExcel(obj, password) -> dict:
    return {
        'Level': ConvertInt(obj.Level(), password),
        'Exp': ConvertLong(obj.Exp(), password),
        'TotalExp': ConvertLong(obj.TotalExp(), password),
    }

def dump_ClanAssistSlotExcel(obj, password) -> dict:
    return {
        'SlotId': ConvertLong(obj.SlotId(), password),
        'EchelonType_': EchelonType(ConvertInt(obj.EchelonType_(), password)).name,
        'SlotNumber': ConvertLong(obj.SlotNumber(), password),
        'AssistTermRewardPeriodFromSec': ConvertLong(obj.AssistTermRewardPeriodFromSec(), password),
        'AssistRewardLimit': ConvertLong(obj.AssistRewardLimit(), password),
        'AssistRentRewardDailyMaxCount': ConvertLong(obj.AssistRentRewardDailyMaxCount(), password),
        'AssistRentalFeeAmount': ConvertLong(obj.AssistRentalFeeAmount(), password),
    }

def dump_ClanChattingEmojiExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ImagePathKr': ConvertString(obj.ImagePathKr(), password),
        'ImagePathJp': ConvertString(obj.ImagePathJp(), password),
        'ImagePathTh': ConvertString(obj.ImagePathTh(), password),
        'ImagePathTw': ConvertString(obj.ImagePathTw(), password),
        'ImagePathEn': ConvertString(obj.ImagePathEn(), password),
        'ImagePathDe': ConvertString(obj.ImagePathDe(), password),
        'ImagePathFr': ConvertString(obj.ImagePathFr(), password),
    }

def dump_ClanRewardExcel(obj, password) -> dict:
    return {
        'ClanRewardType_': ClanRewardType(ConvertInt(obj.ClanRewardType_(), password)).name,
        'EchelonType_': EchelonType(ConvertInt(obj.EchelonType_(), password)).name,
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'RewardParcelAmount': ConvertLong(obj.RewardParcelAmount(), password),
    }

def dump_CombatEmojiExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'EmojiEvent_': EmojiEvent(ConvertInt(obj.EmojiEvent_(), password)).name,
        'OrderOfPriority': ConvertInt(obj.OrderOfPriority(), password),
        'EmojiDuration': obj.EmojiDuration(),
        'EmojiReversal': obj.EmojiReversal(),
        'EmojiTurnOn': obj.EmojiTurnOn(),
        'ShowEmojiDelay': ConvertInt(obj.ShowEmojiDelay(), password),
    }

def dump_ConstArenaExcel(obj, password) -> dict:
    return {
        'AttackCoolTime': ConvertLong(obj.AttackCoolTime(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'DefenseCoolTime': ConvertLong(obj.DefenseCoolTime(), password),
        'TSSStartCoolTime': ConvertLong(obj.TSSStartCoolTime(), password),
        'EndAlarm': ConvertLong(obj.EndAlarm(), password),
        'TimeRewardMaxAmount': ConvertLong(obj.TimeRewardMaxAmount(), password),
        'TicketCost': ConvertLong(obj.TicketCost(), password),
        'DailyRewardResetTime': ConvertString(obj.DailyRewardResetTime(), password),
        'OpenScenarioId': ConvertString(obj.OpenScenarioId(), password),
        'CharacterSlotHideRank': [ConvertLong(obj.CharacterSlotHideRank(j), password) for j in range(obj.CharacterSlotHideRankLength())],
        'MapSlotHideRank': ConvertLong(obj.MapSlotHideRank(), password),
        'RelativeOpponentRankStart': [ConvertLong(obj.RelativeOpponentRankStart(j), password) for j in range(obj.RelativeOpponentRankStartLength())],
        'RelativeOpponentRankEnd': [ConvertLong(obj.RelativeOpponentRankEnd(j), password) for j in range(obj.RelativeOpponentRankEndLength())],
        'ModifiedStatType': [StatType(ConvertInt(obj.ModifiedStatType(j), password)).name for j in range(obj.ModifiedStatTypeLength())],
        'StatMulFactor': [ConvertLong(obj.StatMulFactor(j), password) for j in range(obj.StatMulFactorLength())],
        'StatSumFactor': [ConvertLong(obj.StatSumFactor(j), password) for j in range(obj.StatSumFactorLength())],
        'NPCName': [ConvertString(obj.NPCName(j), password) for j in range(obj.NPCNameLength())],
        'NPCMainCharacterCount': ConvertLong(obj.NPCMainCharacterCount(), password),
        'NPCSupportCharacterCount': ConvertLong(obj.NPCSupportCharacterCount(), password),
        'NPCCharacterSkillLevel': ConvertLong(obj.NPCCharacterSkillLevel(), password),
        'TimeSpanInDaysForBattleHistory': ConvertLong(obj.TimeSpanInDaysForBattleHistory(), password),
        'HiddenCharacterImagePath': ConvertString(obj.HiddenCharacterImagePath(), password),
        'DefenseVictoryRewardMaxCount': ConvertLong(obj.DefenseVictoryRewardMaxCount(), password),
        'TopRankerCountLimit': ConvertLong(obj.TopRankerCountLimit(), password),
        'AutoRefreshIntervalMilliSeconds': ConvertLong(obj.AutoRefreshIntervalMilliSeconds(), password),
        'EchelonSettingIntervalMilliSeconds': ConvertLong(obj.EchelonSettingIntervalMilliSeconds(), password),
        'SkipAllowedTimeMilliSeconds': ConvertLong(obj.SkipAllowedTimeMilliSeconds(), password),
        'ShowSeasonChangeInfoStartTime': ConvertString(obj.ShowSeasonChangeInfoStartTime(), password),
        'ShowSeasonChangeInfoEndTime': ConvertString(obj.ShowSeasonChangeInfoEndTime(), password),
        'ShowSeasonId': ConvertLong(obj.ShowSeasonId(), password),
    }

def dump_ConstAudioExcel(obj, password) -> dict:
    return {
        'DefaultSnapShotName': ConvertString(obj.DefaultSnapShotName(), password),
        'BattleSnapShotName': ConvertString(obj.BattleSnapShotName(), password),
        'RaidSnapShotName': ConvertString(obj.RaidSnapShotName(), password),
        'ExSkillCutInSnapShotName': ConvertString(obj.ExSkillCutInSnapShotName(), password),
    }

def dump_ConstCombatExcel(obj, password) -> dict:
    return {
        'SkillHandCount': ConvertInt(obj.SkillHandCount(), password),
        'DyingTime': ConvertInt(obj.DyingTime(), password),
        'BuffIconBlinkTime': ConvertInt(obj.BuffIconBlinkTime(), password),
        'ShowBufficonEXSkill': obj.ShowBufficonEXSkill(),
        'ShowBufficonPassiveSkill': obj.ShowBufficonPassiveSkill(),
        'ShowBufficonExtraPassiveSkill': obj.ShowBufficonExtraPassiveSkill(),
        'ShowBufficonLeaderSkill': obj.ShowBufficonLeaderSkill(),
        'SuppliesConditionStringId': ConvertString(obj.SuppliesConditionStringId(), password),
        'PublicSpeechBubbleOffsetX': ConvertFloat(obj.PublicSpeechBubbleOffsetX(), password),
        'PublicSpeechBubbleOffsetY': ConvertFloat(obj.PublicSpeechBubbleOffsetY(), password),
        'PublicSpeechBubbleOffsetZ': ConvertFloat(obj.PublicSpeechBubbleOffsetZ(), password),
        'PublicSpeechDuration': ConvertFloat(obj.PublicSpeechDuration(), password),
        'ShowRaidListCount': ConvertInt(obj.ShowRaidListCount(), password),
        'MaxFinalDamage': ConvertLong(obj.MaxFinalDamage(), password),
        'MaxFinalHeal': ConvertLong(obj.MaxFinalHeal(), password),
        'MaxRaidTicketCount': ConvertLong(obj.MaxRaidTicketCount(), password),
        'EngageTimelinePath': ConvertString(obj.EngageTimelinePath(), password),
        'EngageWithSupporterTimelinePath': ConvertString(obj.EngageWithSupporterTimelinePath(), password),
        'VictoryTimelinePath': ConvertString(obj.VictoryTimelinePath(), password),
        'TimeLimitAlarm': ConvertLong(obj.TimeLimitAlarm(), password),
        'EchelonMaxCommonCost': ConvertInt(obj.EchelonMaxCommonCost(), password),
        'EchelonInitCommonCost': ConvertInt(obj.EchelonInitCommonCost(), password),
        'SkillSlotCoolTime': ConvertLong(obj.SkillSlotCoolTime(), password),
        'EnemyRegenCost': ConvertLong(obj.EnemyRegenCost(), password),
        'ChampionRegenCost': ConvertLong(obj.ChampionRegenCost(), password),
        'PlayerRegenCostDelay': ConvertLong(obj.PlayerRegenCostDelay(), password),
        'CrowdControlFactor': ConvertLong(obj.CrowdControlFactor(), password),
        'RaidOpenScenarioId': ConvertString(obj.RaidOpenScenarioId(), password),
        'DefenceConstA': ConvertLong(obj.DefenceConstA(), password),
        'DefenceConstB': ConvertLong(obj.DefenceConstB(), password),
        'DefenceConstC': ConvertLong(obj.DefenceConstC(), password),
        'DefenceConstD': ConvertLong(obj.DefenceConstD(), password),
        'AccuracyConstA': ConvertLong(obj.AccuracyConstA(), password),
        'AccuracyConstB': ConvertLong(obj.AccuracyConstB(), password),
        'AccuracyConstC': ConvertLong(obj.AccuracyConstC(), password),
        'AccuracyConstD': ConvertLong(obj.AccuracyConstD(), password),
        'CriticalConstA': ConvertLong(obj.CriticalConstA(), password),
        'CriticalConstB': ConvertLong(obj.CriticalConstB(), password),
        'CriticalConstC': ConvertLong(obj.CriticalConstC(), password),
        'CriticalConstD': ConvertLong(obj.CriticalConstD(), password),
        'MaxGroupBuffLevel': ConvertInt(obj.MaxGroupBuffLevel(), password),
        'EmojiDefaultTime': ConvertInt(obj.EmojiDefaultTime(), password),
        'TimeLineActionRotateSpeed': ConvertLong(obj.TimeLineActionRotateSpeed(), password),
        'BodyRotateSpeed': ConvertLong(obj.BodyRotateSpeed(), password),
        'NormalTimeScale': ConvertLong(obj.NormalTimeScale(), password),
        'FastTimeScale': ConvertLong(obj.FastTimeScale(), password),
        'BulletTimeScale': ConvertLong(obj.BulletTimeScale(), password),
        'UIDisplayDelayAfterSkillCutIn': ConvertLong(obj.UIDisplayDelayAfterSkillCutIn(), password),
        'UseInitialRangeForCoverMove': obj.UseInitialRangeForCoverMove(),
        'SlowTimeScale': ConvertLong(obj.SlowTimeScale(), password),
        'AimIKMinDegree': ConvertFloat(obj.AimIKMinDegree(), password),
        'AimIKMaxDegree': ConvertFloat(obj.AimIKMaxDegree(), password),
        'MinimumClearTime': ConvertInt(obj.MinimumClearTime(), password),
        'MinimumClearLevelGap': ConvertInt(obj.MinimumClearLevelGap(), password),
        'CheckCheaterMaxUseCostNonArena': ConvertInt(obj.CheckCheaterMaxUseCostNonArena(), password),
        'CheckCheaterMaxUseCostArena': ConvertInt(obj.CheckCheaterMaxUseCostArena(), password),
        'AllowedMaxTimeScale': ConvertLong(obj.AllowedMaxTimeScale(), password),
        'RandomAnimationOutput': ConvertLong(obj.RandomAnimationOutput(), password),
        'SummonedTeleportDistance': ConvertLong(obj.SummonedTeleportDistance(), password),
        'ArenaMinimumClearTime': ConvertInt(obj.ArenaMinimumClearTime(), password),
    }

def dump_ConstCommonExcel(obj, password) -> dict:
    return {
        'CampaignMainStageMaxRank': ConvertInt(obj.CampaignMainStageMaxRank(), password),
        'CampaignMainStageBestRecord': ConvertInt(obj.CampaignMainStageBestRecord(), password),
        'HardAdventurePlayCountRecoverDailyNumber': ConvertInt(obj.HardAdventurePlayCountRecoverDailyNumber(), password),
        'HardStageCount': ConvertInt(obj.HardStageCount(), password),
        'EventContentHardStageCount': ConvertInt(obj.EventContentHardStageCount(), password),
        'TacticRankClearTime': ConvertInt(obj.TacticRankClearTime(), password),
        'BaseTimeScale': ConvertLong(obj.BaseTimeScale(), password),
        'GachaPercentage': ConvertInt(obj.GachaPercentage(), password),
        'AcademyFavorZoneId': ConvertLong(obj.AcademyFavorZoneId(), password),
        'CafePresetSlotCount': ConvertInt(obj.CafePresetSlotCount(), password),
        'CafeMonologueIntervalMillisec': ConvertLong(obj.CafeMonologueIntervalMillisec(), password),
        'CafeMonologueDefaultDuration': ConvertLong(obj.CafeMonologueDefaultDuration(), password),
        'CafeBubbleIdleDurationMilliSec': ConvertLong(obj.CafeBubbleIdleDurationMilliSec(), password),
        'FindGiftTimeLimit': ConvertInt(obj.FindGiftTimeLimit(), password),
        'CafeVisitProbabilityBase': ConvertInt(obj.CafeVisitProbabilityBase(), password),
        'CafeVisitProbabilityTagBonus': ConvertInt(obj.CafeVisitProbabilityTagBonus(), password),
        'CafeAutoChargePeriodInMsc': ConvertInt(obj.CafeAutoChargePeriodInMsc(), password),
        'CafeProductionDecimalPosition': ConvertInt(obj.CafeProductionDecimalPosition(), password),
        'CafeSetGroupApplyCount': ConvertInt(obj.CafeSetGroupApplyCount(), password),
        'WeekDungeonFindGiftRewardLimitCount': ConvertInt(obj.WeekDungeonFindGiftRewardLimitCount(), password),
        'StageFailedCurrencyRefundRate': ConvertInt(obj.StageFailedCurrencyRefundRate(), password),
        'EnterDeposit': ConvertInt(obj.EnterDeposit(), password),
        'AccountMaxLevel': ConvertInt(obj.AccountMaxLevel(), password),
        'MainSquadExpBonus': ConvertInt(obj.MainSquadExpBonus(), password),
        'SupportSquadExpBonus': ConvertInt(obj.SupportSquadExpBonus(), password),
        'AccountExpRatio': ConvertInt(obj.AccountExpRatio(), password),
        'MissionToastLifeTime': ConvertInt(obj.MissionToastLifeTime(), password),
        'ExpItemInsertLimit': ConvertInt(obj.ExpItemInsertLimit(), password),
        'ExpItemInsertAccelTime': ConvertInt(obj.ExpItemInsertAccelTime(), password),
        'CharacterLvUpCoefficient': ConvertInt(obj.CharacterLvUpCoefficient(), password),
        'EquipmentLvUpCoefficient': ConvertInt(obj.EquipmentLvUpCoefficient(), password),
        'ExpEquipInsertLimit': ConvertInt(obj.ExpEquipInsertLimit(), password),
        'EquipLvUpCoefficient': ConvertInt(obj.EquipLvUpCoefficient(), password),
        'NicknameLength': ConvertInt(obj.NicknameLength(), password),
        'CraftDuration': [ConvertInt(obj.CraftDuration(j), password) for j in range(obj.CraftDurationLength())],
        'CraftLimitTime': ConvertInt(obj.CraftLimitTime(), password),
        'CraftTicketItemUniqueId': ConvertInt(obj.CraftTicketItemUniqueId(), password),
        'CraftTicketConsumeAmount': ConvertInt(obj.CraftTicketConsumeAmount(), password),
        'AcademyTicketCost': ConvertInt(obj.AcademyTicketCost(), password),
        'MassangerMessageExpireDay': ConvertInt(obj.MassangerMessageExpireDay(), password),
        'CraftLeafNodeGenerateLv1Count': ConvertInt(obj.CraftLeafNodeGenerateLv1Count(), password),
        'CraftLeafNodeGenerateLv2Count': ConvertInt(obj.CraftLeafNodeGenerateLv2Count(), password),
        'TutorialGachaShopId': ConvertInt(obj.TutorialGachaShopId(), password),
        'TutorialGachaGoodsId': ConvertInt(obj.TutorialGachaGoodsId(), password),
        'EquipmentSlotOpenLevel': [ConvertInt(obj.EquipmentSlotOpenLevel(j), password) for j in range(obj.EquipmentSlotOpenLevelLength())],
        'ScenarioAutoDelayMillisec': ConvertFloat(obj.ScenarioAutoDelayMillisec(), password),
        'JoinOrCreateClanCoolTimeFromHour': ConvertLong(obj.JoinOrCreateClanCoolTimeFromHour(), password),
        'ClanMaxMember': ConvertLong(obj.ClanMaxMember(), password),
        'ClanSearchResultCount': ConvertLong(obj.ClanSearchResultCount(), password),
        'ClanMaxApplicant': ConvertLong(obj.ClanMaxApplicant(), password),
        'ClanRejoinCoolTimeFromSecond': ConvertLong(obj.ClanRejoinCoolTimeFromSecond(), password),
        'ClanWordBalloonMaxCharacter': ConvertInt(obj.ClanWordBalloonMaxCharacter(), password),
        'CallNameRenameCoolTimeFromHour': ConvertLong(obj.CallNameRenameCoolTimeFromHour(), password),
        'CallNameMinimumLength': ConvertLong(obj.CallNameMinimumLength(), password),
        'CallNameMaximumLength': ConvertLong(obj.CallNameMaximumLength(), password),
        'LobbyToScreenModeWaitTime': ConvertLong(obj.LobbyToScreenModeWaitTime(), password),
        'ScreenshotToLobbyButtonHideDelay': ConvertLong(obj.ScreenshotToLobbyButtonHideDelay(), password),
        'PrologueScenarioID01': ConvertLong(obj.PrologueScenarioID01(), password),
        'PrologueScenarioID02': ConvertLong(obj.PrologueScenarioID02(), password),
        'TutorialHardStage11': ConvertLong(obj.TutorialHardStage11(), password),
        'TutorialSpeedButtonStage': ConvertLong(obj.TutorialSpeedButtonStage(), password),
        'TutorialCharacterDefaultCount': ConvertLong(obj.TutorialCharacterDefaultCount(), password),
        'TutorialShopCategoryType': ShopCategoryType(ConvertInt(obj.TutorialShopCategoryType(), password)).name,
        'AdventureStrategyPlayTimeLimitInSeconds': ConvertLong(obj.AdventureStrategyPlayTimeLimitInSeconds(), password),
        'EventStrategyPlayTimeLimitInSeconds': ConvertLong(obj.EventStrategyPlayTimeLimitInSeconds(), password),
        'WeekDungoenTacticPlayTimeLimitInSeconds': ConvertLong(obj.WeekDungoenTacticPlayTimeLimitInSeconds(), password),
        'RaidTacticPlayTimeLimitInSeconds': ConvertLong(obj.RaidTacticPlayTimeLimitInSeconds(), password),
        'RaidOpponentListAmount': ConvertLong(obj.RaidOpponentListAmount(), password),
        'CraftBaseGoldRequired': [ConvertLong(obj.CraftBaseGoldRequired(j), password) for j in range(obj.CraftBaseGoldRequiredLength())],
        'PostExpiredDayAttendance': ConvertInt(obj.PostExpiredDayAttendance(), password),
        'PostExpiredDayInventoryOverflow': ConvertInt(obj.PostExpiredDayInventoryOverflow(), password),
        'PostExpiredDayGameManager': ConvertInt(obj.PostExpiredDayGameManager(), password),
        'UILabelCharacterWrap': ConvertString(obj.UILabelCharacterWrap(), password),
        'RequestTimeOut': ConvertFloat(obj.RequestTimeOut(), password),
        'MailStorageSoftCap': ConvertInt(obj.MailStorageSoftCap(), password),
        'MailStorageHardCap': ConvertInt(obj.MailStorageHardCap(), password),
        'ClearDeckStorageSize': ConvertInt(obj.ClearDeckStorageSize(), password),
        'ClearDeckNoStarViewCount': ConvertInt(obj.ClearDeckNoStarViewCount(), password),
        'ClearDeck1StarViewCount': ConvertInt(obj.ClearDeck1StarViewCount(), password),
        'ClearDeck2StarViewCount': ConvertInt(obj.ClearDeck2StarViewCount(), password),
        'ClearDeck3StarViewCount': ConvertInt(obj.ClearDeck3StarViewCount(), password),
        'ExSkillLevelMax': ConvertInt(obj.ExSkillLevelMax(), password),
        'PublicSkillLevelMax': ConvertInt(obj.PublicSkillLevelMax(), password),
        'PassiveSkillLevelMax': ConvertInt(obj.PassiveSkillLevelMax(), password),
        'ExtraPassiveSkillLevelMax': ConvertInt(obj.ExtraPassiveSkillLevelMax(), password),
        'AccountCommentMaxLength': ConvertInt(obj.AccountCommentMaxLength(), password),
        'FormationCollider01OffsetX': ConvertLong(obj.FormationCollider01OffsetX(), password),
        'FormationCollider01OffsetY': ConvertLong(obj.FormationCollider01OffsetY(), password),
        'FormationCollider01OffsetZ': ConvertLong(obj.FormationCollider01OffsetZ(), password),
        'FormationCollider01SizeX': ConvertLong(obj.FormationCollider01SizeX(), password),
        'FormationCollider01SizeY': ConvertLong(obj.FormationCollider01SizeY(), password),
        'FormationCollider01SizeZ': ConvertLong(obj.FormationCollider01SizeZ(), password),
        'FormationCollider02OffsetX': ConvertLong(obj.FormationCollider02OffsetX(), password),
        'FormationCollider02OffsetY': ConvertLong(obj.FormationCollider02OffsetY(), password),
        'FormationCollider02OffsetZ': ConvertLong(obj.FormationCollider02OffsetZ(), password),
        'FormationCollider02SizeX': ConvertLong(obj.FormationCollider02SizeX(), password),
        'FormationCollider02SizeY': ConvertLong(obj.FormationCollider02SizeY(), password),
        'FormationCollider02SizeZ': ConvertLong(obj.FormationCollider02SizeZ(), password),
        'FormationCollider03OffsetX': ConvertLong(obj.FormationCollider03OffsetX(), password),
        'FormationCollider03OffsetY': ConvertLong(obj.FormationCollider03OffsetY(), password),
        'FormationCollider03OffsetZ': ConvertLong(obj.FormationCollider03OffsetZ(), password),
        'FormationCollider03SizeX': ConvertLong(obj.FormationCollider03SizeX(), password),
        'FormationCollider03SizeY': ConvertLong(obj.FormationCollider03SizeY(), password),
        'FormationCollider03SizeZ': ConvertLong(obj.FormationCollider03SizeZ(), password),
        'ShowFurnitureTag': obj.ShowFurnitureTag(),
        'CafeSummonCoolTimeFromHour': ConvertInt(obj.CafeSummonCoolTimeFromHour(), password),
        'LimitedStageDailyClearCount': ConvertLong(obj.LimitedStageDailyClearCount(), password),
        'LimitedStageEntryTimeLimit': ConvertLong(obj.LimitedStageEntryTimeLimit(), password),
        'LimitedStageEntryTimeBuffer': ConvertLong(obj.LimitedStageEntryTimeBuffer(), password),
        'LimitedStagePointAmount': ConvertLong(obj.LimitedStagePointAmount(), password),
        'LimitedStagePointPerApMin': ConvertLong(obj.LimitedStagePointPerApMin(), password),
        'LimitedStagePointPerApMax': ConvertLong(obj.LimitedStagePointPerApMax(), password),
        'AccountLinkReward': ConvertInt(obj.AccountLinkReward(), password),
        'MonthlyProductCheckDays': ConvertInt(obj.MonthlyProductCheckDays(), password),
        'WeaponLvUpCoefficient': ConvertInt(obj.WeaponLvUpCoefficient(), password),
        'ShowRaidMyListCount': ConvertInt(obj.ShowRaidMyListCount(), password),
        'MaxLevelExpMasterCoinRatio': ConvertInt(obj.MaxLevelExpMasterCoinRatio(), password),
        'MasterCoinItemId': ConvertLong(obj.MasterCoinItemId(), password),
        'CallnameLengthEn': ConvertInt(obj.CallnameLengthEn(), password),
        'CallnameLengthKr': ConvertInt(obj.CallnameLengthKr(), password),
        'NicknameLengthKr': ConvertInt(obj.NicknameLengthKr(), password),
        'ClanNameLength': ConvertInt(obj.ClanNameLength(), password),
    }

def dump_ConstStrategyExcel(obj, password) -> dict:
    return {
        'HexaMapBoundaryOffset': ConvertFloat(obj.HexaMapBoundaryOffset(), password),
        'HexaMapStartCameraOffset': ConvertFloat(obj.HexaMapStartCameraOffset(), password),
        'CameraZoomMax': ConvertFloat(obj.CameraZoomMax(), password),
        'CameraZoomMin': ConvertFloat(obj.CameraZoomMin(), password),
        'CameraZoomDefault': ConvertFloat(obj.CameraZoomDefault(), password),
        'HealCostType': CurrencyTypes(ConvertInt(obj.HealCostType(), password)).name,
        'HealCostAmount': [ConvertLong(obj.HealCostAmount(j), password) for j in range(obj.HealCostAmountLength())],
        'CanHealHpRate': ConvertInt(obj.CanHealHpRate(), password),
        'PlayTimeLimitInSeconds': ConvertLong(obj.PlayTimeLimitInSeconds(), password),
        'AdventureEchelonCount': ConvertInt(obj.AdventureEchelonCount(), password),
        'RaidEchelonCount': ConvertInt(obj.RaidEchelonCount(), password),
        'DefaultEchelonCount': ConvertInt(obj.DefaultEchelonCount(), password),
        'EventContentEchelonCount': ConvertInt(obj.EventContentEchelonCount(), password),
    }

def dump_ContentsFeverExcel(obj, password) -> dict:
    return {
        'ConditionContent': FeverBattleType(ConvertInt(obj.ConditionContent(), password)).name,
        'SkillFeverCheckCondition': SkillPriorityCheckTarget(ConvertInt(obj.SkillFeverCheckCondition(), password)).name,
        'SkillCostFever': ConvertLong(obj.SkillCostFever(), password),
        'FeverStartTime': ConvertLong(obj.FeverStartTime(), password),
        'FeverDurationTime': ConvertLong(obj.FeverDurationTime(), password),
    }

def dump_ContentsScenarioExcel(obj, password) -> dict:
    return {
        'Id': ConvertUInt(obj.Id(), password),
        'LocalizeId': ConvertUInt(obj.LocalizeId(), password),
        'ScenarioContentType_': ScenarioContentType(ConvertInt(obj.ScenarioContentType_(), password)).name,
        'ScenarioGroupId': [ConvertLong(obj.ScenarioGroupId(j), password) for j in range(obj.ScenarioGroupIdLength())],
    }

def dump_CouponStuffExcel(obj, password) -> dict:
    return {
        'StuffId': ConvertLong(obj.StuffId(), password),
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelId': ConvertLong(obj.ParcelId(), password),
        'LimitAmount': ConvertInt(obj.LimitAmount(), password),
        'CouponStuffNameLocalizeKey': ConvertString(obj.CouponStuffNameLocalizeKey(), password),
    }

def dump_CumulativeTimeRewardExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Description': ConvertString(obj.Description(), password),
        'StartDate': ConvertString(obj.StartDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'TimeCondition': [ConvertLong(obj.TimeCondition(j), password) for j in range(obj.TimeConditionLength())],
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardId': [ConvertLong(obj.RewardId(j), password) for j in range(obj.RewardIdLength())],
        'RewardAmount': [ConvertInt(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_CurrencyExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'CurrencyType': CurrencyTypes(ConvertInt(obj.CurrencyType(), password)).name,
        'CurrencyName': ConvertString(obj.CurrencyName(), password),
        'Icon': ConvertString(obj.Icon(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'AutoChargeMsc': ConvertInt(obj.AutoChargeMsc(), password),
        'AutoChargeAmount': ConvertInt(obj.AutoChargeAmount(), password),
        'CurrencyOverChargeType_': CurrencyOverChargeType(ConvertInt(obj.CurrencyOverChargeType_(), password)).name,
        'CurrencyAdditionalChargeType_': CurrencyAdditionalChargeType(ConvertInt(obj.CurrencyAdditionalChargeType_(), password)).name,
        'ChargeLimit': ConvertLong(obj.ChargeLimit(), password),
        'OverChargeLimit': ConvertLong(obj.OverChargeLimit(), password),
        'SpriteName': ConvertString(obj.SpriteName(), password),
        'DailyRefillAmount': ConvertLong(obj.DailyRefillAmount(), password),
        'DailyRefillTime': [ConvertLong(obj.DailyRefillTime(j), password) for j in range(obj.DailyRefillTimeLength())],
    }

def dump_DefaultCharacterExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'FavoriteCharacter': obj.FavoriteCharacter(),
        'Level': ConvertInt(obj.Level(), password),
        'Exp': ConvertInt(obj.Exp(), password),
        'FavorExp': ConvertInt(obj.FavorExp(), password),
        'FavorRank': ConvertInt(obj.FavorRank(), password),
        'StarGrade': ConvertInt(obj.StarGrade(), password),
        'ExSkillLevel': ConvertInt(obj.ExSkillLevel(), password),
        'PassiveSkillLevel': ConvertInt(obj.PassiveSkillLevel(), password),
        'ExtraPassiveSkillLevel': ConvertInt(obj.ExtraPassiveSkillLevel(), password),
        'CommonSkillLevel': ConvertInt(obj.CommonSkillLevel(), password),
        'LeaderSkillLevel': ConvertInt(obj.LeaderSkillLevel(), password),
    }

def dump_DefaultEchelonExcel(obj, password) -> dict:
    return {
        'EchlonId': ConvertInt(obj.EchlonId(), password),
        'LeaderId': ConvertLong(obj.LeaderId(), password),
        'MainId': [ConvertLong(obj.MainId(j), password) for j in range(obj.MainIdLength())],
        'SupportId': [ConvertLong(obj.SupportId(j), password) for j in range(obj.SupportIdLength())],
        'TssId': ConvertLong(obj.TssId(), password),
    }

def dump_DefaultFurnitureExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Location': FurnitureLocation(ConvertInt(obj.Location(), password)).name,
        'PositionX': ConvertFloat(obj.PositionX(), password),
        'PositionY': ConvertFloat(obj.PositionY(), password),
        'Rotation': ConvertFloat(obj.Rotation(), password),
    }

def dump_DefaultMailExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeCodeId': ConvertUInt(obj.LocalizeCodeId(), password),
        'MailType_': MailType(ConvertInt(obj.MailType_(), password)).name,
        'MailSendPeriodFrom': ConvertString(obj.MailSendPeriodFrom(), password),
        'MailSendPeriodTo': ConvertString(obj.MailSendPeriodTo(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_DefaultParcelExcel(obj, password) -> dict:
    return {
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelId': ConvertLong(obj.ParcelId(), password),
        'ParcelAmount': ConvertLong(obj.ParcelAmount(), password),
    }

def dump_EmoticonSpecialExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'CharacterUniqueId': ConvertLong(obj.CharacterUniqueId(), password),
        'Random': ConvertString(obj.Random(), password),
    }

def dump_EquipmentExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EquipmentCategory_': EquipmentCategory(ConvertInt(obj.EquipmentCategory_(), password)).name,
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'Wear': obj.Wear(),
        'MaxLevel': ConvertInt(obj.MaxLevel(), password),
        'RecipeId': ConvertInt(obj.RecipeId(), password),
        'TierInit': ConvertLong(obj.TierInit(), password),
        'NextTierEquipment': ConvertLong(obj.NextTierEquipment(), password),
        'StackableMax': ConvertInt(obj.StackableMax(), password),
        'Icon': ConvertString(obj.Icon(), password),
        'ImageName': ConvertString(obj.ImageName(), password),
        'Tags': [Tag(ConvertInt(obj.Tags(j), password)).name for j in range(obj.TagsLength())],
        'CraftQuality': ConvertLong(obj.CraftQuality(), password),
        'ShopCategory': [ShopCategoryType(ConvertInt(obj.ShopCategory(j), password)).name for j in range(obj.ShopCategoryLength())],
        'ShortcutTypeId': ConvertLong(obj.ShortcutTypeId(), password),
    }

def dump_EquipmentLevelExcel(obj, password) -> dict:
    return {
        'Level': ConvertInt(obj.Level(), password),
        'TierLevelExp': [ConvertLong(obj.TierLevelExp(j), password) for j in range(obj.TierLevelExpLength())],
        'TotalExp': [ConvertLong(obj.TotalExp(j), password) for j in range(obj.TotalExpLength())],
    }

def dump_EquipmentStatExcel(obj, password) -> dict:
    return {
        'EquipmentId': ConvertLong(obj.EquipmentId(), password),
        'StatLevelUpType_': StatLevelUpType(ConvertInt(obj.StatLevelUpType_(), password)).name,
        'StatType': [EquipmentOptionType(ConvertInt(obj.StatType(j), password)).name for j in range(obj.StatTypeLength())],
        'MinStat': [ConvertLong(obj.MinStat(j), password) for j in range(obj.MinStatLength())],
        'MaxStat': [ConvertLong(obj.MaxStat(j), password) for j in range(obj.MaxStatLength())],
        'LevelUpInsertLimit': ConvertInt(obj.LevelUpInsertLimit(), password),
        'LevelUpFeedExp': ConvertLong(obj.LevelUpFeedExp(), password),
        'LevelUpFeedCostCurrency': CurrencyTypes(ConvertInt(obj.LevelUpFeedCostCurrency(), password)).name,
        'LevelUpFeedCostAmount': ConvertLong(obj.LevelUpFeedCostAmount(), password),
        'EquipmentCategory_': EquipmentCategory(ConvertInt(obj.EquipmentCategory_(), password)).name,
        'LevelUpFeedAddExp': ConvertLong(obj.LevelUpFeedAddExp(), password),
        'DefaultMaxLevel': ConvertInt(obj.DefaultMaxLevel(), password),
        'TranscendenceMax': ConvertInt(obj.TranscendenceMax(), password),
        'DamageFactorGroupId': ConvertString(obj.DamageFactorGroupId(), password),
    }

def dump_EventContentBoxGachaElementExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'Round': ConvertLong(obj.Round(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
    }

def dump_EventContentBoxGachaManageExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Round': ConvertLong(obj.Round(), password),
        'GoodsId': ConvertLong(obj.GoodsId(), password),
        'IsLoop': obj.IsLoop(),
    }

def dump_EventContentBoxGachaShopExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'GroupElementAmount': ConvertLong(obj.GroupElementAmount(), password),
        'Round': ConvertLong(obj.Round(), password),
        'IsLegacy': obj.IsLegacy(),
        'IsPrize': obj.IsPrize(),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
    }

def dump_EventContentBuffExcel(obj, password) -> dict:
    return {
        'EventContentBuffId': ConvertLong(obj.EventContentBuffId(), password),
        'IsBuff': obj.IsBuff(),
        'CharacterTag': Tag(ConvertInt(obj.CharacterTag(), password)).name,
        'SkillGroupId': ConvertString(obj.SkillGroupId(), password),
        'IconPath': ConvertString(obj.IconPath(), password),
        'SpriteName': ConvertString(obj.SpriteName(), password),
        'BuffDescriptionLocalizeCodeId': ConvertString(obj.BuffDescriptionLocalizeCodeId(), password),
        'BuffDescriptionIconPath': ConvertString(obj.BuffDescriptionIconPath(), password),
    }

def dump_EventContentBuffGroupExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'BuffContentId': ConvertLong(obj.BuffContentId(), password),
        'BuffGroupId': ConvertLong(obj.BuffGroupId(), password),
        'BuffGroupNameLocalizeCodeId': ConvertString(obj.BuffGroupNameLocalizeCodeId(), password),
        'EventContentBuffId1': ConvertLong(obj.EventContentBuffId1(), password),
        'BuffNameLocalizeCodeId1': ConvertString(obj.BuffNameLocalizeCodeId1(), password),
        'EventContentBuffId2': ConvertLong(obj.EventContentBuffId2(), password),
        'BuffNameLocalizeCodeId2': ConvertString(obj.BuffNameLocalizeCodeId2(), password),
        'EventContentDebuffId': ConvertLong(obj.EventContentDebuffId(), password),
        'DebuffNameLocalizeCodeId': ConvertString(obj.DebuffNameLocalizeCodeId(), password),
        'BuffGroupProb': ConvertLong(obj.BuffGroupProb(), password),
    }

def dump_EventContentCardExcel(obj, password) -> dict:
    return {
        'CardGroupId': ConvertInt(obj.CardGroupId(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'IconPath': ConvertString(obj.IconPath(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
    }

def dump_EventContentCardShopExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'CostGoodsId': ConvertLong(obj.CostGoodsId(), password),
        'IsLegacy': obj.IsLegacy(),
        'CardGroupId': ConvertInt(obj.CardGroupId(), password),
        'RefreshGroup': ConvertInt(obj.RefreshGroup(), password),
        'Prob': ConvertInt(obj.Prob(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_EventContentCharacterBonusExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'EventContentItemType_': [EventContentItemType(ConvertInt(obj.EventContentItemType_(j), password)).name for j in range(obj.EventContentItemType_Length())],
        'BonusPercentage': [ConvertLong(obj.BonusPercentage(j), password) for j in range(obj.BonusPercentageLength())],
    }

def dump_EventContentCollectionExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'UnlockConditionType': EventCollectionUnlockType(ConvertInt(obj.UnlockConditionType(), password)).name,
        'UnlockConditionParameter': ConvertLong(obj.UnlockConditionParameter(), password),
        'UnlockConditionCount': ConvertLong(obj.UnlockConditionCount(), password),
        'IsObject': obj.IsObject(),
        'IsHorizon': obj.IsHorizon(),
        'ThumbResource': ConvertString(obj.ThumbResource(), password),
        'FullResource': ConvertString(obj.FullResource(), password),
    }

def dump_EventContentCurrencyItemExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'EventContentItemType_': EventContentItemType(ConvertInt(obj.EventContentItemType_(), password)).name,
        'ItemUniqueId': ConvertLong(obj.ItemUniqueId(), password),
    }

def dump_EventContentDebuffRewardExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'EventStageId': ConvertLong(obj.EventStageId(), password),
        'EventContentItemType_': EventContentItemType(ConvertInt(obj.EventContentItemType_(), password)).name,
        'RewardPercentage': ConvertLong(obj.RewardPercentage(), password),
    }

def dump_EventContentExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'BgImagePath': ConvertString(obj.BgImagePath(), password),
    }

def dump_EventContentMissionExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'GroupName': ConvertString(obj.GroupName(), password),
        'Category': MissionCategory(ConvertInt(obj.Category(), password)).name,
        'Description': ConvertString(obj.Description(), password),
        'ResetType': MissionResetType(ConvertInt(obj.ResetType(), password)).name,
        'ViewFlag': obj.ViewFlag(),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'PreMissionId': [ConvertLong(obj.PreMissionId(j), password) for j in range(obj.PreMissionIdLength())],
        'AccountType': AccountState(ConvertInt(obj.AccountType(), password)).name,
        'AccountLevel': ConvertLong(obj.AccountLevel(), password),
        'ShortcutUI': [ConvertString(obj.ShortcutUI(j), password) for j in range(obj.ShortcutUILength())],
        'CompleteConditionType': MissionCompleteConditionType(ConvertInt(obj.CompleteConditionType(), password)).name,
        'CompleteConditionCount': ConvertLong(obj.CompleteConditionCount(), password),
        'CompleteConditionParameter': [ConvertLong(obj.CompleteConditionParameter(j), password) for j in range(obj.CompleteConditionParameterLength())],
        'CompleteConditionParameterName': [ConvertString(obj.CompleteConditionParameterName(j), password) for j in range(obj.CompleteConditionParameterNameLength())],
        'RewardIcon': ConvertString(obj.RewardIcon(), password),
        'MissionRewardParcelType': [ParcelType(ConvertInt(obj.MissionRewardParcelType(j), password)).name for j in range(obj.MissionRewardParcelTypeLength())],
        'MissionRewardParcelId': [ConvertLong(obj.MissionRewardParcelId(j), password) for j in range(obj.MissionRewardParcelIdLength())],
        'MissionRewardAmount': [ConvertInt(obj.MissionRewardAmount(j), password) for j in range(obj.MissionRewardAmountLength())],
    }

def dump_EventContentPlayGuideExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'DisplayOrder': ConvertInt(obj.DisplayOrder(), password),
        'GuideTitle': ConvertString(obj.GuideTitle(), password),
        'GuideImagePath': ConvertString(obj.GuideImagePath(), password),
        'GuideText': ConvertString(obj.GuideText(), password),
    }

def dump_EventContentScenarioExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Order': ConvertLong(obj.Order(), password),
        'RecollectionNumber': ConvertLong(obj.RecollectionNumber(), password),
        'IsRecollection': obj.IsRecollection(),
        'ScenarioGroupId': [ConvertLong(obj.ScenarioGroupId(j), password) for j in range(obj.ScenarioGroupIdLength())],
        'ScenarioConditionType': EventContentScenarioConditionType(ConvertInt(obj.ScenarioConditionType(), password)).name,
        'ConditionAmount': ConvertLong(obj.ConditionAmount(), password),
        'ClearedScenarioGroupId': ConvertLong(obj.ClearedScenarioGroupId(), password),
        'RecollectionSummaryLocalizeScenarioId': ConvertUInt(obj.RecollectionSummaryLocalizeScenarioId(), password),
        'RecollectionResource': ConvertString(obj.RecollectionResource(), password),
        'IsRecollectionHorizon': obj.IsRecollectionHorizon(),
        'CostParcelType': ParcelType(ConvertInt(obj.CostParcelType(), password)).name,
        'CostId': ConvertLong(obj.CostId(), password),
        'CostAmount': ConvertInt(obj.CostAmount(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardId': [ConvertLong(obj.RewardId(j), password) for j in range(obj.RewardIdLength())],
        'RewardAmount': [ConvertInt(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_EventContentSeasonExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Name': ConvertString(obj.Name(), password),
        'EventContentType_': EventContentType(ConvertInt(obj.EventContentType_(), password)).name,
        'OpenConditionContent_': OpenConditionContent(ConvertInt(obj.OpenConditionContent_(), password)).name,
        'ContentLockType_': ContentLockType(ConvertInt(obj.ContentLockType_(), password)).name,
        'EventDisplay': obj.EventDisplay(),
        'EventItemId': ConvertLong(obj.EventItemId(), password),
        'BeforehandExposedTime': ConvertString(obj.BeforehandExposedTime(), password),
        'EventContentOpenTime': ConvertString(obj.EventContentOpenTime(), password),
        'EventContentCloseTime': ConvertString(obj.EventContentCloseTime(), password),
        'ExtensionTime': ConvertString(obj.ExtensionTime(), password),
        'MainIconParcelPath': ConvertString(obj.MainIconParcelPath(), password),
        'SubIconParcelPath': ConvertString(obj.SubIconParcelPath(), password),
        'BeforehandBgImagePath': ConvertString(obj.BeforehandBgImagePath(), password),
        'MinigamePrologScenarioGroupId': ConvertLong(obj.MinigamePrologScenarioGroupId(), password),
        'BeforehandScenarioGroupId': [ConvertLong(obj.BeforehandScenarioGroupId(j), password) for j in range(obj.BeforehandScenarioGroupIdLength())],
        'MainBannerImagePath': ConvertString(obj.MainBannerImagePath(), password),
        'MainBgImagePath': ConvertString(obj.MainBgImagePath(), password),
    }

def dump_EventContentShopExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'SalePeriodFrom': ConvertString(obj.SalePeriodFrom(), password),
        'SalePeriodTo': ConvertString(obj.SalePeriodTo(), password),
        'PurchaseCooltimeMin': ConvertLong(obj.PurchaseCooltimeMin(), password),
        'PurchaseCountLimit': ConvertLong(obj.PurchaseCountLimit(), password),
        'PurchaseCountResetType_': PurchaseCountResetType(ConvertInt(obj.PurchaseCountResetType_(), password)).name,
        'BuyReportEventName': ConvertString(obj.BuyReportEventName(), password),
    }

def dump_EventContentShopInfoExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'LocalizeCode': ConvertUInt(obj.LocalizeCode(), password),
        'CostParcelType': ParcelType(ConvertInt(obj.CostParcelType(), password)).name,
        'CostParcelId': ConvertLong(obj.CostParcelId(), password),
        'IsRefresh': obj.IsRefresh(),
        'AutoRefreshCoolTime': ConvertLong(obj.AutoRefreshCoolTime(), password),
        'RefreshAbleCount': ConvertLong(obj.RefreshAbleCount(), password),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'OpenPeriodFrom': ConvertString(obj.OpenPeriodFrom(), password),
        'OpenPeriodTo': ConvertString(obj.OpenPeriodTo(), password),
    }

def dump_EventContentShopRefreshExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': ConvertLong(obj.GoodsId(), password),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'RefreshGroup': ConvertInt(obj.RefreshGroup(), password),
        'Prob': ConvertInt(obj.Prob(), password),
        'BuyReportEventName': ConvertString(obj.BuyReportEventName(), password),
    }

def dump_EventContentSpecialOperationsExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'PointItemId': ConvertLong(obj.PointItemId(), password),
    }

def dump_EventContentSpineDialogOffsetExcel(obj, password) -> dict:
    return {
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'EventContentType_': EventContentType(ConvertInt(obj.EventContentType_(), password)).name,
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'SpineOffsetX': ConvertFloat(obj.SpineOffsetX(), password),
        'SpineOffsetY': ConvertFloat(obj.SpineOffsetY(), password),
        'DialogOffsetX': ConvertFloat(obj.DialogOffsetX(), password),
        'DialogOffsetY': ConvertFloat(obj.DialogOffsetY(), password),
    }

def dump_EventContentStageExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Name': ConvertString(obj.Name(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'StageDifficulty_': StageDifficulty(ConvertInt(obj.StageDifficulty_(), password)).name,
        'StageNumber': ConvertInt(obj.StageNumber(), password),
        'StageDisplay': ConvertInt(obj.StageDisplay(), password),
        'PrevStageId': ConvertLong(obj.PrevStageId(), password),
        'OpenDate': ConvertLong(obj.OpenDate(), password),
        'OpenEventPoint': ConvertLong(obj.OpenEventPoint(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'StageEnterCostType': ParcelType(ConvertInt(obj.StageEnterCostType(), password)).name,
        'StageEnterCostId': ConvertLong(obj.StageEnterCostId(), password),
        'StageEnterCostAmount': ConvertInt(obj.StageEnterCostAmount(), password),
        'StageEnterEchelonCount': ConvertInt(obj.StageEnterEchelonCount(), password),
        'StarConditionTacticRankSCount': ConvertLong(obj.StarConditionTacticRankSCount(), password),
        'StarConditionTurnCount': ConvertLong(obj.StarConditionTurnCount(), password),
        'EnterScenarioGroupId': [ConvertLong(obj.EnterScenarioGroupId(j), password) for j in range(obj.EnterScenarioGroupIdLength())],
        'ClearScenarioGroupId': [ConvertLong(obj.ClearScenarioGroupId(j), password) for j in range(obj.ClearScenarioGroupIdLength())],
        'StrategyMap': ConvertString(obj.StrategyMap(), password),
        'StrategyMapBG': ConvertString(obj.StrategyMapBG(), password),
        'EventContentStageRewardId': ConvertLong(obj.EventContentStageRewardId(), password),
        'MaxTurn': ConvertInt(obj.MaxTurn(), password),
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'RecommandLevel': ConvertInt(obj.RecommandLevel(), password),
        'BgmId': ConvertString(obj.BgmId(), password),
        'StrategyEnvironment_': StrategyEnvironment(ConvertInt(obj.StrategyEnvironment_(), password)).name,
        'GroundID': ConvertLong(obj.GroundID(), password),
        'ContentType_': ContentType(ConvertInt(obj.ContentType_(), password)).name,
        'BGMId': ConvertLong(obj.BGMId(), password),
        'InstantClear': obj.InstantClear(),
        'BuffContentId': ConvertLong(obj.BuffContentId(), password),
        'ChallengeDisplay': obj.ChallengeDisplay(),
    }

def dump_EventContentStageRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'RewardTag_': RewardTag(ConvertInt(obj.RewardTag_(), password)).name,
        'RewardProb': ConvertInt(obj.RewardProb(), password),
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardId': ConvertLong(obj.RewardId(), password),
        'RewardAmount': ConvertInt(obj.RewardAmount(), password),
        'IsDisplayed': obj.IsDisplayed(),
    }

def dump_EventContentStageTotalRewardExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'RequiredEventItemAmount': ConvertLong(obj.RequiredEventItemAmount(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_FavorLevelExcel(obj, password) -> dict:
    return {
        'Level': ConvertLong(obj.Level(), password),
        'ExpType': [ConvertLong(obj.ExpType(j), password) for j in range(obj.ExpTypeLength())],
    }

def dump_FavorLevelRewardExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'FavorLevel': ConvertLong(obj.FavorLevel(), password),
        'StatType': [EquipmentOptionType(ConvertInt(obj.StatType(j), password)).name for j in range(obj.StatTypeLength())],
        'StatValue': [ConvertLong(obj.StatValue(j), password) for j in range(obj.StatValueLength())],
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardAmount': [ConvertLong(obj.RewardAmount(j), password) for j in range(obj.RewardAmountLength())],
    }

def dump_FixedEchelonSettingExcel(obj, password) -> dict:
    return {
        'FixedEchelonID': ConvertLong(obj.FixedEchelonID(), password),
        'MainLeaderSlot': ConvertInt(obj.MainLeaderSlot(), password),
        'MainCharacterID': [ConvertLong(obj.MainCharacterID(j), password) for j in range(obj.MainCharacterIDLength())],
        'MainLevel': [ConvertInt(obj.MainLevel(j), password) for j in range(obj.MainLevelLength())],
        'MainGrade': [ConvertInt(obj.MainGrade(j), password) for j in range(obj.MainGradeLength())],
        'MainExSkillLevel': [ConvertInt(obj.MainExSkillLevel(j), password) for j in range(obj.MainExSkillLevelLength())],
        'MainNoneExSkillLevel': [ConvertInt(obj.MainNoneExSkillLevel(j), password) for j in range(obj.MainNoneExSkillLevelLength())],
        'MainEquipment1ID': [ConvertLong(obj.MainEquipment1ID(j), password) for j in range(obj.MainEquipment1IDLength())],
        'MainEquipment1Level': [ConvertInt(obj.MainEquipment1Level(j), password) for j in range(obj.MainEquipment1LevelLength())],
        'MainEquipment2ID': [ConvertLong(obj.MainEquipment2ID(j), password) for j in range(obj.MainEquipment2IDLength())],
        'MainEquipment2Level': [ConvertInt(obj.MainEquipment2Level(j), password) for j in range(obj.MainEquipment2LevelLength())],
        'MainEquipment3ID': [ConvertLong(obj.MainEquipment3ID(j), password) for j in range(obj.MainEquipment3IDLength())],
        'MainEquipment3Level': [ConvertInt(obj.MainEquipment3Level(j), password) for j in range(obj.MainEquipment3LevelLength())],
        'SupportCharacterID': [ConvertLong(obj.SupportCharacterID(j), password) for j in range(obj.SupportCharacterIDLength())],
        'SupportLevel': [ConvertInt(obj.SupportLevel(j), password) for j in range(obj.SupportLevelLength())],
        'SupportGrade': [ConvertInt(obj.SupportGrade(j), password) for j in range(obj.SupportGradeLength())],
        'SupportExSkillLevel': [ConvertInt(obj.SupportExSkillLevel(j), password) for j in range(obj.SupportExSkillLevelLength())],
        'SupportNoneExSkillLevel': [ConvertInt(obj.SupportNoneExSkillLevel(j), password) for j in range(obj.SupportNoneExSkillLevelLength())],
        'SupportEquipment1ID': [ConvertLong(obj.SupportEquipment1ID(j), password) for j in range(obj.SupportEquipment1IDLength())],
        'SupportEquipment1Level': [ConvertInt(obj.SupportEquipment1Level(j), password) for j in range(obj.SupportEquipment1LevelLength())],
        'SupportEquipment2ID': [ConvertLong(obj.SupportEquipment2ID(j), password) for j in range(obj.SupportEquipment2IDLength())],
        'SupportEquipment2Level': [ConvertInt(obj.SupportEquipment2Level(j), password) for j in range(obj.SupportEquipment2LevelLength())],
        'SupportEquipment3ID': [ConvertLong(obj.SupportEquipment3ID(j), password) for j in range(obj.SupportEquipment3IDLength())],
        'SupportEquipment3Level': [ConvertInt(obj.SupportEquipment3Level(j), password) for j in range(obj.SupportEquipment3LevelLength())],
    }

def dump_FloaterCommonExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'TacticEntityType_': TacticEntityType(ConvertInt(obj.TacticEntityType_(), password)).name,
        'FloaterOffsetPosX': ConvertInt(obj.FloaterOffsetPosX(), password),
        'FloaterOffsetPosY': ConvertInt(obj.FloaterOffsetPosY(), password),
        'FloaterRandomPosRangeX': ConvertInt(obj.FloaterRandomPosRangeX(), password),
        'FloaterRandomPosRangeY': ConvertInt(obj.FloaterRandomPosRangeY(), password),
    }

def dump_FormationLocationExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'GroupID': ConvertLong(obj.GroupID(), password),
        'SlotZ': [ConvertFloat(obj.SlotZ(j), password) for j in range(obj.SlotZLength())],
        'SlotX': [ConvertFloat(obj.SlotX(j), password) for j in range(obj.SlotXLength())],
    }

def dump_FurnitureExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'Category': FurnitureCategory(ConvertInt(obj.Category(), password)).name,
        'SubCategory': FurnitureSubCategory(ConvertInt(obj.SubCategory(), password)).name,
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'StarGradeInit': ConvertInt(obj.StarGradeInit(), password),
        'Tier': ConvertLong(obj.Tier(), password),
        'Icon': ConvertString(obj.Icon(), password),
        'SizeWidth': ConvertInt(obj.SizeWidth(), password),
        'SizeHeight': ConvertInt(obj.SizeHeight(), password),
        'OtherSize': ConvertInt(obj.OtherSize(), password),
        'ExpandWidth': ConvertInt(obj.ExpandWidth(), password),
        'Enable': obj.Enable(),
        'ReverseRotation': obj.ReverseRotation(),
        'Prefab': ConvertString(obj.Prefab(), password),
        'PrefabExpand': ConvertString(obj.PrefabExpand(), password),
        'SubPrefab': ConvertString(obj.SubPrefab(), password),
        'SubExpandPrefab': ConvertString(obj.SubExpandPrefab(), password),
        'CornerPrefab': ConvertString(obj.CornerPrefab(), password),
        'StackableMax': ConvertLong(obj.StackableMax(), password),
        'RecipeCraftId': ConvertLong(obj.RecipeCraftId(), password),
        'SetGroudpId': ConvertLong(obj.SetGroudpId(), password),
        'ComfortBonus': ConvertLong(obj.ComfortBonus(), password),
        'VisitOperationType': ConvertLong(obj.VisitOperationType(), password),
        'VisitBonusOperationType': ConvertLong(obj.VisitBonusOperationType(), password),
        'Tags': [Tag(ConvertInt(obj.Tags(j), password)).name for j in range(obj.TagsLength())],
        'CraftQuality': ConvertLong(obj.CraftQuality(), password),
        'EventCollectionId': ConvertLong(obj.EventCollectionId(), password),
        'EventCollectionBubbleOffsetX': ConvertLong(obj.EventCollectionBubbleOffsetX(), password),
        'EventCollectionBubbleOffsetY': ConvertLong(obj.EventCollectionBubbleOffsetY(), password),
        'MultipleConditionCheckType_': MultipleConditionCheckType(ConvertInt(obj.MultipleConditionCheckType_(), password)).name,
        'CafeCharacterState_': [CafeCharacterState(ConvertInt(obj.CafeCharacterState_(j), password)).name for j in range(obj.CafeCharacterState_Length())],
    }

def dump_FurnitureGroupExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'GroupNameLocalize': ConvertUInt(obj.GroupNameLocalize(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'RequiredFurnitureCount': [ConvertInt(obj.RequiredFurnitureCount(j), password) for j in range(obj.RequiredFurnitureCountLength())],
        'ComfortBonus': [ConvertLong(obj.ComfortBonus(j), password) for j in range(obj.ComfortBonusLength())],
    }

def dump_GachaCraftNodeExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'Tier': ConvertLong(obj.Tier(), password),
        'Tag_': [Tag(ConvertInt(obj.Tag_(j), password)).name for j in range(obj.Tag_Length())],
        'NodeQuality': ConvertLong(obj.NodeQuality(), password),
        'Lv1Exp': ConvertLong(obj.Lv1Exp(), password),
        'Lv2Exp': ConvertLong(obj.Lv2Exp(), password),
        'Icon': ConvertString(obj.Icon(), password),
        'LocalizeKey': ConvertUInt(obj.LocalizeKey(), password),
        'Lv1Property': ConvertLong(obj.Lv1Property(), password),
        'Lv2Property': ConvertLong(obj.Lv2Property(), password),
        'GP100': ConvertInt(obj.GP100(), password),
        'GP101': ConvertInt(obj.GP101(), password),
        'GP102': ConvertInt(obj.GP102(), password),
        'GP103': ConvertInt(obj.GP103(), password),
        'GP120': ConvertInt(obj.GP120(), password),
        'GP121': ConvertInt(obj.GP121(), password),
        'GP122': ConvertInt(obj.GP122(), password),
        'GP123': ConvertInt(obj.GP123(), password),
        'GP140': ConvertInt(obj.GP140(), password),
        'GP141': ConvertInt(obj.GP141(), password),
        'GP142': ConvertInt(obj.GP142(), password),
        'GP143': ConvertInt(obj.GP143(), password),
        'GP130': ConvertInt(obj.GP130(), password),
        'GP131': ConvertInt(obj.GP131(), password),
        'GP132': ConvertInt(obj.GP132(), password),
        'GP133': ConvertInt(obj.GP133(), password),
        'GP112': ConvertInt(obj.GP112(), password),
        'GP151': ConvertInt(obj.GP151(), password),
        'GP152': ConvertInt(obj.GP152(), password),
        'GP153': ConvertInt(obj.GP153(), password),
        'GP2100': ConvertInt(obj.GP2100(), password),
        'GP2101': ConvertInt(obj.GP2101(), password),
        'GP2102': ConvertInt(obj.GP2102(), password),
        'GP2103': ConvertInt(obj.GP2103(), password),
        'GP2000': ConvertInt(obj.GP2000(), password),
        'GP2001': ConvertInt(obj.GP2001(), password),
        'GP2002': ConvertInt(obj.GP2002(), password),
        'GP2003': ConvertInt(obj.GP2003(), password),
        'GP2004': ConvertInt(obj.GP2004(), password),
        'GP2005': ConvertInt(obj.GP2005(), password),
        'GP2006': ConvertInt(obj.GP2006(), password),
        'GP2007': ConvertInt(obj.GP2007(), password),
        'GP2008': ConvertInt(obj.GP2008(), password),
        'GP2009': ConvertInt(obj.GP2009(), password),
        'GP1100': ConvertInt(obj.GP1100(), password),
        'GP1101': ConvertInt(obj.GP1101(), password),
        'GP1102': ConvertInt(obj.GP1102(), password),
        'GP1103': ConvertInt(obj.GP1103(), password),
        'GP1104': ConvertInt(obj.GP1104(), password),
        'GP1105': ConvertInt(obj.GP1105(), password),
        'GP1106': ConvertInt(obj.GP1106(), password),
        'GP1107': ConvertInt(obj.GP1107(), password),
        'GP1108': ConvertInt(obj.GP1108(), password),
        'GP1109': ConvertInt(obj.GP1109(), password),
        'GP1110': ConvertInt(obj.GP1110(), password),
        'GP1111': ConvertInt(obj.GP1111(), password),
        'GP1112': ConvertInt(obj.GP1112(), password),
        'GP1000': ConvertInt(obj.GP1000(), password),
        'GP1001': ConvertInt(obj.GP1001(), password),
        'GP1002': ConvertInt(obj.GP1002(), password),
        'GP1003': ConvertInt(obj.GP1003(), password),
        'GP1004': ConvertInt(obj.GP1004(), password),
        'GP1005': ConvertInt(obj.GP1005(), password),
        'GP1007': ConvertInt(obj.GP1007(), password),
        'GP1008': ConvertInt(obj.GP1008(), password),
    }

def dump_GachaElementExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'GachaGroupID': ConvertLong(obj.GachaGroupID(), password),
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelID': ConvertLong(obj.ParcelID(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'ParcelAmountMin': ConvertInt(obj.ParcelAmountMin(), password),
        'ParcelAmountMax': ConvertInt(obj.ParcelAmountMax(), password),
        'Prob': ConvertInt(obj.Prob(), password),
        'State': ConvertInt(obj.State(), password),
    }

def dump_GachaElementRecursiveExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'GachaGroupID': ConvertLong(obj.GachaGroupID(), password),
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelID': ConvertLong(obj.ParcelID(), password),
        'ParcelAmountMin': ConvertInt(obj.ParcelAmountMin(), password),
        'ParcelAmountMax': ConvertInt(obj.ParcelAmountMax(), password),
        'Prob': ConvertInt(obj.Prob(), password),
        'State': ConvertInt(obj.State(), password),
    }

def dump_GachaGroupExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'NameKr': ConvertString(obj.NameKr(), password),
        'IsRecursive': obj.IsRecursive(),
        'GroupType': GachaGroupType(ConvertInt(obj.GroupType(), password)).name,
    }

def dump_GoodsExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Type': ConvertInt(obj.Type(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'IconPath': ConvertString(obj.IconPath(), password),
        'ConsumeParcelType': [ParcelType(ConvertInt(obj.ConsumeParcelType(j), password)).name for j in range(obj.ConsumeParcelTypeLength())],
        'ConsumeParcelId': [ConvertLong(obj.ConsumeParcelId(j), password) for j in range(obj.ConsumeParcelIdLength())],
        'ConsumeParcelAmount': [ConvertLong(obj.ConsumeParcelAmount(j), password) for j in range(obj.ConsumeParcelAmountLength())],
        'ConsumeCondition': [ConvertString(obj.ConsumeCondition(j), password) for j in range(obj.ConsumeConditionLength())],
        'ConsumeExtraStep': [ConvertLong(obj.ConsumeExtraStep(j), password) for j in range(obj.ConsumeExtraStepLength())],
        'ConsumeExtraAmount': [ConvertLong(obj.ConsumeExtraAmount(j), password) for j in range(obj.ConsumeExtraAmountLength())],
        'State': ConvertInt(obj.State(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ParcelAmount': [ConvertLong(obj.ParcelAmount(j), password) for j in range(obj.ParcelAmountLength())],
    }

def dump_GroundExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'StageFileName': [ConvertString(obj.StageFileName(j), password) for j in range(obj.StageFileNameLength())],
        'GroundSceneName': ConvertString(obj.GroundSceneName(), password),
        'FormationGroupId': ConvertLong(obj.FormationGroupId(), password),
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'EnemyArmorType': ArmorType(ConvertInt(obj.EnemyArmorType(), password)).name,
        'LevelMinion': ConvertLong(obj.LevelMinion(), password),
        'LevelElite': ConvertLong(obj.LevelElite(), password),
        'LevelChampion': ConvertLong(obj.LevelChampion(), password),
        'LevelBoss': ConvertLong(obj.LevelBoss(), password),
        'ObstacleLevel': ConvertLong(obj.ObstacleLevel(), password),
        'GradeMinion': ConvertLong(obj.GradeMinion(), password),
        'GradeElite': ConvertLong(obj.GradeElite(), password),
        'GradeChampion': ConvertLong(obj.GradeChampion(), password),
        'GradeBoss': ConvertLong(obj.GradeBoss(), password),
        'PlayerSightPointAdd': ConvertLong(obj.PlayerSightPointAdd(), password),
        'PlayerSightPointRate': ConvertLong(obj.PlayerSightPointRate(), password),
        'PlayerAttackRangeAdd': ConvertLong(obj.PlayerAttackRangeAdd(), password),
        'PlayerAttackRangeRate': ConvertLong(obj.PlayerAttackRangeRate(), password),
        'EnemySightPointAdd': ConvertLong(obj.EnemySightPointAdd(), password),
        'EnemySightPointRate': ConvertLong(obj.EnemySightPointRate(), password),
        'EnemyAttackRangeAdd': ConvertLong(obj.EnemyAttackRangeAdd(), password),
        'EnemyAttackRangeRate': ConvertLong(obj.EnemyAttackRangeRate(), password),
        'PlayerSkillRangeAdd': ConvertLong(obj.PlayerSkillRangeAdd(), password),
        'PlayerSkillRangeRate': ConvertLong(obj.PlayerSkillRangeRate(), password),
        'EnemySkillRangeAdd': ConvertLong(obj.EnemySkillRangeAdd(), password),
        'EnemySkillRangeRate': ConvertLong(obj.EnemySkillRangeRate(), password),
        'TSSAirUnitHeight': ConvertLong(obj.TSSAirUnitHeight(), password),
        'IsRaid': obj.IsRaid(),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'WarningUI': obj.WarningUI(),
        'TSSHatchOpen': obj.TSSHatchOpen(),
    }

def dump_GroundGridFlat(obj, password) -> dict:
    return {
        'X': ConvertInt(obj.X(), password),
        'Y': ConvertInt(obj.Y(), password),
        'StartX': ConvertFloat(obj.StartX(), password),
        'StartY': ConvertFloat(obj.StartY(), password),
        'Gap': ConvertFloat(obj.Gap(), password),
        'Nodes': [dump_GroundNodeFlat(obj.Nodes(j), password) for j in range(obj.NodesLength())],
        'Version': ConvertString(obj.Version(), password),
    }

def dump_GroundNodeFlat(obj, password) -> dict:
    return {
        'X': ConvertInt(obj.X(), password),
        'Y': ConvertInt(obj.Y(), password),
        'IsCanNotUseSkill': obj.IsCanNotUseSkill(),
        'Position': dump_GroundVector3(obj.Position(), password),
        'NodeType': GroundNodeType(ConvertInt(obj.NodeType(), password)).name,
        'OriginalNodeType': GroundNodeType(ConvertInt(obj.OriginalNodeType(), password)).name,
    }

def dump_GroundModuleRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertUInt(obj.GroupId(), password),
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'RewardParcelAmount': ConvertLong(obj.RewardParcelAmount(), password),
        'RewardParcelProbability': ConvertLong(obj.RewardParcelProbability(), password),
        'IsDisplayed': obj.IsDisplayed(),
        'DropItemModelPrefabPath': ConvertString(obj.DropItemModelPrefabPath(), password),
    }

def dump_GuideMissionExcel(obj, password) -> dict:
    return {
        'SeasonId': ConvertLong(obj.SeasonId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'Category': MissionCategory(ConvertInt(obj.Category(), password)).name,
        'IsLegacy': obj.IsLegacy(),
        'LoginCount': ConvertLong(obj.LoginCount(), password),
        'PreMissionId': [ConvertLong(obj.PreMissionId(j), password) for j in range(obj.PreMissionIdLength())],
        'Description': ConvertString(obj.Description(), password),
        'ShortcutUI': [ConvertString(obj.ShortcutUI(j), password) for j in range(obj.ShortcutUILength())],
        'CompleteConditionType': MissionCompleteConditionType(ConvertInt(obj.CompleteConditionType(), password)).name,
        'CompleteConditionCount': ConvertLong(obj.CompleteConditionCount(), password),
        'CompleteConditionParameter': [ConvertLong(obj.CompleteConditionParameter(j), password) for j in range(obj.CompleteConditionParameterLength())],
        'CompleteConditionParameterName': ConvertString(obj.CompleteConditionParameterName(), password),
        'MissionRewardParcelType': [ParcelType(ConvertInt(obj.MissionRewardParcelType(j), password)).name for j in range(obj.MissionRewardParcelTypeLength())],
        'MissionRewardParcelId': [ConvertLong(obj.MissionRewardParcelId(j), password) for j in range(obj.MissionRewardParcelIdLength())],
        'MissionRewardAmount': [ConvertInt(obj.MissionRewardAmount(j), password) for j in range(obj.MissionRewardAmountLength())],
    }

def dump_GuideMissionSeasonExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'TitleLocalizeCode': ConvertString(obj.TitleLocalizeCode(), password),
        'InfomationLocalizeCode': ConvertString(obj.InfomationLocalizeCode(), password),
        'AccountType': AccountState(ConvertInt(obj.AccountType(), password)).name,
        'Enabled': obj.Enabled(),
        'StartDate': ConvertString(obj.StartDate(), password),
        'StartableEndDate': ConvertString(obj.StartableEndDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'CloseBannerAfterCompletion': obj.CloseBannerAfterCompletion(),
        'MaximumLoginCount': ConvertLong(obj.MaximumLoginCount(), password),
        'ExpiryDate': ConvertLong(obj.ExpiryDate(), password),
        'SpineCharacterId': ConvertLong(obj.SpineCharacterId(), password),
        'RequirementParcelImage': ConvertString(obj.RequirementParcelImage(), password),
        'RewardImage': ConvertString(obj.RewardImage(), password),
        'LobbyBannerImage': ConvertString(obj.LobbyBannerImage(), password),
        'BackgroundImage': ConvertString(obj.BackgroundImage(), password),
        'TitleImage': ConvertString(obj.TitleImage(), password),
        'RequirementParcelType': ParcelType(ConvertInt(obj.RequirementParcelType(), password)).name,
        'RequirementParcelId': ConvertLong(obj.RequirementParcelId(), password),
        'RequirementParcelAmount': ConvertInt(obj.RequirementParcelAmount(), password),
    }

def dump_HpBarAbbreviationExcel(obj, password) -> dict:
    return {
        'MonsterLv': ConvertInt(obj.MonsterLv(), password),
        'StandardHpBar': ConvertInt(obj.StandardHpBar(), password),
        'RaidBossHpBar': ConvertInt(obj.RaidBossHpBar(), password),
    }

def dump_InformationExcel(obj, password) -> dict:
    return {
        'GroupID': ConvertLong(obj.GroupID(), password),
        'PageName': ConvertString(obj.PageName(), password),
        'TutorialParentName': [ConvertString(obj.TutorialParentName(j), password) for j in range(obj.TutorialParentNameLength())],
        'UIName': [ConvertString(obj.UIName(j), password) for j in range(obj.UINameLength())],
    }

def dump_InformationStrategyObjectExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'StageId': ConvertLong(obj.StageId(), password),
        'PageName': ConvertString(obj.PageName(), password),
    }

def dump_ItemExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Rarity_': Rarity(ConvertInt(obj.Rarity_(), password)).name,
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'ItemCategory_': ItemCategory(ConvertInt(obj.ItemCategory_(), password)).name,
        'Quality': ConvertLong(obj.Quality(), password),
        'Icon': ConvertString(obj.Icon(), password),
        'SpriteName': ConvertString(obj.SpriteName(), password),
        'StackableMax': ConvertInt(obj.StackableMax(), password),
        'StackableFunction': ConvertInt(obj.StackableFunction(), password),
        'ImmediateUse': obj.ImmediateUse(),
        'UsingResultParcelType': ParcelType(ConvertInt(obj.UsingResultParcelType(), password)).name,
        'UsingResultId': ConvertLong(obj.UsingResultId(), password),
        'UsingResultAmount': ConvertLong(obj.UsingResultAmount(), password),
        'MailType_': MailType(ConvertInt(obj.MailType_(), password)).name,
        'ExpiryChangeParcelType': ParcelType(ConvertInt(obj.ExpiryChangeParcelType(), password)).name,
        'ExpiryChangeId': ConvertLong(obj.ExpiryChangeId(), password),
        'ExpiryChangeAmount': ConvertLong(obj.ExpiryChangeAmount(), password),
        'CanTierUpgrade': obj.CanTierUpgrade(),
        'TierUpgradeRecipeCraftId': ConvertLong(obj.TierUpgradeRecipeCraftId(), password),
        'Tags': [Tag(ConvertInt(obj.Tags(j), password)).name for j in range(obj.TagsLength())],
        'CraftQuality': ConvertLong(obj.CraftQuality(), password),
        'ShopCategory': [ShopCategoryType(ConvertInt(obj.ShopCategory(j), password)).name for j in range(obj.ShopCategoryLength())],
        'ExpirationDateTime': ConvertString(obj.ExpirationDateTime(), password),
        'ShortcutTypeId': ConvertLong(obj.ShortcutTypeId(), password),
        'IsThreeGachaItem': obj.IsThreeGachaItem(),
    }

def dump_KatakanaConvertExcel(obj, password) -> dict:
    return {
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
    }

def dump_KnockBackExcel(obj, password) -> dict:
    return {
        'Index': ConvertLong(obj.Index(), password),
        'Dist': ConvertFloat(obj.Dist(), password),
        'Speed': ConvertFloat(obj.Speed(), password),
    }

def dump_LimitedStageExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Name': ConvertString(obj.Name(), password),
        'SeasonId': ConvertLong(obj.SeasonId(), password),
        'StageDifficulty_': StageDifficulty(ConvertInt(obj.StageDifficulty_(), password)).name,
        'StageNumber': ConvertInt(obj.StageNumber(), password),
        'StageDisplay': ConvertInt(obj.StageDisplay(), password),
        'PrevStageId': ConvertLong(obj.PrevStageId(), password),
        'OpenDate': ConvertLong(obj.OpenDate(), password),
        'OpenEventPoint': ConvertLong(obj.OpenEventPoint(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'StageEnterCostType': CurrencyTypes(ConvertInt(obj.StageEnterCostType(), password)).name,
        'StageEnterCostAmount': ConvertInt(obj.StageEnterCostAmount(), password),
        'StageEnterEchelonCount': ConvertInt(obj.StageEnterEchelonCount(), password),
        'StarConditionTacticRankSCount': ConvertLong(obj.StarConditionTacticRankSCount(), password),
        'StarConditionTurnCount': ConvertLong(obj.StarConditionTurnCount(), password),
        'EnterScenarioGroupId': [ConvertLong(obj.EnterScenarioGroupId(j), password) for j in range(obj.EnterScenarioGroupIdLength())],
        'ClearScenarioGroupId': [ConvertLong(obj.ClearScenarioGroupId(j), password) for j in range(obj.ClearScenarioGroupIdLength())],
        'StrategyMap': ConvertString(obj.StrategyMap(), password),
        'StrategyMapBG': ConvertString(obj.StrategyMapBG(), password),
        'StageRewardId': ConvertLong(obj.StageRewardId(), password),
        'MaxTurn': ConvertInt(obj.MaxTurn(), password),
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'RecommandLevel': ConvertInt(obj.RecommandLevel(), password),
        'BgmId': ConvertString(obj.BgmId(), password),
        'StrategyEnvironment_': StrategyEnvironment(ConvertInt(obj.StrategyEnvironment_(), password)).name,
        'GroundID': ConvertLong(obj.GroundID(), password),
        'ContentType_': ContentType(ConvertInt(obj.ContentType_(), password)).name,
        'BGMId': ConvertLong(obj.BGMId(), password),
        'InstantClear': obj.InstantClear(),
        'BuffContentId': ConvertLong(obj.BuffContentId(), password),
        'ChallengeDisplay': obj.ChallengeDisplay(),
    }

def dump_LimitedStageRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'RewardTag_': RewardTag(ConvertInt(obj.RewardTag_(), password)).name,
        'RewardProb': ConvertInt(obj.RewardProb(), password),
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardId': ConvertLong(obj.RewardId(), password),
        'RewardAmount': ConvertInt(obj.RewardAmount(), password),
        'IsDisplayed': obj.IsDisplayed(),
    }

def dump_LimitedStageSeasonExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'StartDate': ConvertString(obj.StartDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'TypeACount': ConvertLong(obj.TypeACount(), password),
        'TypeBCount': ConvertLong(obj.TypeBCount(), password),
        'TypeCCount': ConvertLong(obj.TypeCCount(), password),
    }

def dump_LoadingImageExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'ImagePathKr': ConvertString(obj.ImagePathKr(), password),
        'ImagePathJp': ConvertString(obj.ImagePathJp(), password),
        'ImagePathTh': ConvertString(obj.ImagePathTh(), password),
        'ImagePathTw': ConvertString(obj.ImagePathTw(), password),
        'ImagePathEn': ConvertString(obj.ImagePathEn(), password),
        'ImagePathDe': ConvertString(obj.ImagePathDe(), password),
        'ImagePathFr': ConvertString(obj.ImagePathFr(), password),
        'DisplayWeight': ConvertInt(obj.DisplayWeight(), password),
    }

def dump_LocalizeCharProfileExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'StatusMessageKr': ConvertString(obj.StatusMessageKr(), password),
        'StatusMessageJp': ConvertString(obj.StatusMessageJp(), password),
        'StatusMessageTh': ConvertString(obj.StatusMessageTh(), password),
        'StatusMessageTw': ConvertString(obj.StatusMessageTw(), password),
        'StatusMessageEn': ConvertString(obj.StatusMessageEn(), password),
        'StatusMessageDe': ConvertString(obj.StatusMessageDe(), password),
        'StatusMessageFr': ConvertString(obj.StatusMessageFr(), password),
        'FullNameKr': ConvertString(obj.FullNameKr(), password),
        'FullNameJp': ConvertString(obj.FullNameJp(), password),
        'FullNameTh': ConvertString(obj.FullNameTh(), password),
        'FullNameTw': ConvertString(obj.FullNameTw(), password),
        'FullNameEn': ConvertString(obj.FullNameEn(), password),
        'FullNameDe': ConvertString(obj.FullNameDe(), password),
        'FullNameFr': ConvertString(obj.FullNameFr(), password),
        'FamilyNameKr': ConvertString(obj.FamilyNameKr(), password),
        'FamilyNameRubyKr': ConvertString(obj.FamilyNameRubyKr(), password),
        'PersonalNameKr': ConvertString(obj.PersonalNameKr(), password),
        'PersonalNameRubyKr': ConvertString(obj.PersonalNameRubyKr(), password),
        'FamilyNameJp': ConvertString(obj.FamilyNameJp(), password),
        'FamilyNameRubyJp': ConvertString(obj.FamilyNameRubyJp(), password),
        'PersonalNameJp': ConvertString(obj.PersonalNameJp(), password),
        'PersonalNameRubyJp': ConvertString(obj.PersonalNameRubyJp(), password),
        'FamilyNameTh': ConvertString(obj.FamilyNameTh(), password),
        'FamilyNameRubyTh': ConvertString(obj.FamilyNameRubyTh(), password),
        'PersonalNameTh': ConvertString(obj.PersonalNameTh(), password),
        'PersonalNameRubyTh': ConvertString(obj.PersonalNameRubyTh(), password),
        'FamilyNameTw': ConvertString(obj.FamilyNameTw(), password),
        'FamilyNameRubyTw': ConvertString(obj.FamilyNameRubyTw(), password),
        'PersonalNameTw': ConvertString(obj.PersonalNameTw(), password),
        'PersonalNameRubyTw': ConvertString(obj.PersonalNameRubyTw(), password),
        'FamilyNameEn': ConvertString(obj.FamilyNameEn(), password),
        'FamilyNameRubyEn': ConvertString(obj.FamilyNameRubyEn(), password),
        'PersonalNameEn': ConvertString(obj.PersonalNameEn(), password),
        'PersonalNameRubyEn': ConvertString(obj.PersonalNameRubyEn(), password),
        'FamilyNameDe': ConvertString(obj.FamilyNameDe(), password),
        'FamilyNameRubyDe': ConvertString(obj.FamilyNameRubyDe(), password),
        'PersonalNameDe': ConvertString(obj.PersonalNameDe(), password),
        'PersonalNameRubyDe': ConvertString(obj.PersonalNameRubyDe(), password),
        'FamilyNameFr': ConvertString(obj.FamilyNameFr(), password),
        'FamilyNameRubyFr': ConvertString(obj.FamilyNameRubyFr(), password),
        'PersonalNameFr': ConvertString(obj.PersonalNameFr(), password),
        'PersonalNameRubyFr': ConvertString(obj.PersonalNameRubyFr(), password),
        'SchoolYearKr': ConvertString(obj.SchoolYearKr(), password),
        'SchoolYearJp': ConvertString(obj.SchoolYearJp(), password),
        'SchoolYearTh': ConvertString(obj.SchoolYearTh(), password),
        'SchoolYearTw': ConvertString(obj.SchoolYearTw(), password),
        'SchoolYearEn': ConvertString(obj.SchoolYearEn(), password),
        'SchoolYearDe': ConvertString(obj.SchoolYearDe(), password),
        'SchoolYearFr': ConvertString(obj.SchoolYearFr(), password),
        'CharacterAgeKr': ConvertString(obj.CharacterAgeKr(), password),
        'CharacterAgeJp': ConvertString(obj.CharacterAgeJp(), password),
        'CharacterAgeTh': ConvertString(obj.CharacterAgeTh(), password),
        'CharacterAgeTw': ConvertString(obj.CharacterAgeTw(), password),
        'CharacterAgeEn': ConvertString(obj.CharacterAgeEn(), password),
        'CharacterAgeDe': ConvertString(obj.CharacterAgeDe(), password),
        'CharacterAgeFr': ConvertString(obj.CharacterAgeFr(), password),
        'BirthDay': ConvertString(obj.BirthDay(), password),
        'BirthdayKr': ConvertString(obj.BirthdayKr(), password),
        'BirthdayJp': ConvertString(obj.BirthdayJp(), password),
        'BirthdayTh': ConvertString(obj.BirthdayTh(), password),
        'BirthdayTw': ConvertString(obj.BirthdayTw(), password),
        'BirthdayEn': ConvertString(obj.BirthdayEn(), password),
        'BirthdayDe': ConvertString(obj.BirthdayDe(), password),
        'BirthdayFr': ConvertString(obj.BirthdayFr(), password),
        'CharHeightKr': ConvertString(obj.CharHeightKr(), password),
        'CharHeightJp': ConvertString(obj.CharHeightJp(), password),
        'CharHeightTh': ConvertString(obj.CharHeightTh(), password),
        'CharHeightTw': ConvertString(obj.CharHeightTw(), password),
        'CharHeightEn': ConvertString(obj.CharHeightEn(), password),
        'CharHeightDe': ConvertString(obj.CharHeightDe(), password),
        'CharHeightFr': ConvertString(obj.CharHeightFr(), password),
        'ArtistNameKr': ConvertString(obj.ArtistNameKr(), password),
        'ArtistNameJp': ConvertString(obj.ArtistNameJp(), password),
        'ArtistNameTh': ConvertString(obj.ArtistNameTh(), password),
        'ArtistNameTw': ConvertString(obj.ArtistNameTw(), password),
        'ArtistNameEn': ConvertString(obj.ArtistNameEn(), password),
        'ArtistNameDe': ConvertString(obj.ArtistNameDe(), password),
        'ArtistNameFr': ConvertString(obj.ArtistNameFr(), password),
        'CharacterVoiceKr': ConvertString(obj.CharacterVoiceKr(), password),
        'CharacterVoiceJp': ConvertString(obj.CharacterVoiceJp(), password),
        'CharacterVoiceTh': ConvertString(obj.CharacterVoiceTh(), password),
        'CharacterVoiceTw': ConvertString(obj.CharacterVoiceTw(), password),
        'CharacterVoiceEn': ConvertString(obj.CharacterVoiceEn(), password),
        'CharacterVoiceDe': ConvertString(obj.CharacterVoiceDe(), password),
        'CharacterVoiceFr': ConvertString(obj.CharacterVoiceFr(), password),
        'HobbyKr': ConvertString(obj.HobbyKr(), password),
        'HobbyJp': ConvertString(obj.HobbyJp(), password),
        'HobbyTh': ConvertString(obj.HobbyTh(), password),
        'HobbyTw': ConvertString(obj.HobbyTw(), password),
        'HobbyEn': ConvertString(obj.HobbyEn(), password),
        'HobbyDe': ConvertString(obj.HobbyDe(), password),
        'HobbyFr': ConvertString(obj.HobbyFr(), password),
        'WeaponNameKr': ConvertString(obj.WeaponNameKr(), password),
        'WeaponDescKr': ConvertString(obj.WeaponDescKr(), password),
        'WeaponNameJp': ConvertString(obj.WeaponNameJp(), password),
        'WeaponDescJp': ConvertString(obj.WeaponDescJp(), password),
        'WeaponNameTh': ConvertString(obj.WeaponNameTh(), password),
        'WeaponDescTh': ConvertString(obj.WeaponDescTh(), password),
        'WeaponNameTw': ConvertString(obj.WeaponNameTw(), password),
        'WeaponDescTw': ConvertString(obj.WeaponDescTw(), password),
        'WeaponNameEn': ConvertString(obj.WeaponNameEn(), password),
        'WeaponDescEn': ConvertString(obj.WeaponDescEn(), password),
        'WeaponNameDe': ConvertString(obj.WeaponNameDe(), password),
        'WeaponDescDe': ConvertString(obj.WeaponDescDe(), password),
        'WeaponNameFr': ConvertString(obj.WeaponNameFr(), password),
        'WeaponDescFr': ConvertString(obj.WeaponDescFr(), password),
        'ProfileIntroductionKr': ConvertString(obj.ProfileIntroductionKr(), password),
        'ProfileIntroductionJp': ConvertString(obj.ProfileIntroductionJp(), password),
        'ProfileIntroductionTh': ConvertString(obj.ProfileIntroductionTh(), password),
        'ProfileIntroductionTw': ConvertString(obj.ProfileIntroductionTw(), password),
        'ProfileIntroductionEn': ConvertString(obj.ProfileIntroductionEn(), password),
        'ProfileIntroductionDe': ConvertString(obj.ProfileIntroductionDe(), password),
        'ProfileIntroductionFr': ConvertString(obj.ProfileIntroductionFr(), password),
        'CharacterSSRNewKr': ConvertString(obj.CharacterSSRNewKr(), password),
        'CharacterSSRNewJp': ConvertString(obj.CharacterSSRNewJp(), password),
        'CharacterSSRNewTh': ConvertString(obj.CharacterSSRNewTh(), password),
        'CharacterSSRNewTw': ConvertString(obj.CharacterSSRNewTw(), password),
        'CharacterSSRNewEn': ConvertString(obj.CharacterSSRNewEn(), password),
        'CharacterSSRNewDe': ConvertString(obj.CharacterSSRNewDe(), password),
        'CharacterSSRNewFr': ConvertString(obj.CharacterSSRNewFr(), password),
    }

def dump_LocalizeCodeExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeCodeInBuildExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeErrorExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'ErrorLevel': WebAPIErrorLevel(ConvertInt(obj.ErrorLevel(), password)).name,
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeEtcExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'NameKr': ConvertString(obj.NameKr(), password),
        'DescriptionKr': ConvertString(obj.DescriptionKr(), password),
        'NameJp': ConvertString(obj.NameJp(), password),
        'DescriptionJp': ConvertString(obj.DescriptionJp(), password),
        'NameTh': ConvertString(obj.NameTh(), password),
        'DescriptionTh': ConvertString(obj.DescriptionTh(), password),
        'NameTw': ConvertString(obj.NameTw(), password),
        'DescriptionTw': ConvertString(obj.DescriptionTw(), password),
        'NameEn': ConvertString(obj.NameEn(), password),
        'DescriptionEn': ConvertString(obj.DescriptionEn(), password),
        'NameDe': ConvertString(obj.NameDe(), password),
        'DescriptionDe': ConvertString(obj.DescriptionDe(), password),
        'NameFr': ConvertString(obj.NameFr(), password),
        'DescriptionFr': ConvertString(obj.DescriptionFr(), password),
    }

def dump_LocalizeGachaShopExcel(obj, password) -> dict:
    return {
        'GachaShopId': ConvertLong(obj.GachaShopId(), password),
        'TabNameKr': ConvertString(obj.TabNameKr(), password),
        'TabNameJp': ConvertString(obj.TabNameJp(), password),
        'TabNameTh': ConvertString(obj.TabNameTh(), password),
        'TabNameTw': ConvertString(obj.TabNameTw(), password),
        'TabNameEn': ConvertString(obj.TabNameEn(), password),
        'TabNameDe': ConvertString(obj.TabNameDe(), password),
        'TabNameFr': ConvertString(obj.TabNameFr(), password),
        'TitleNameKr': ConvertString(obj.TitleNameKr(), password),
        'TitleNameJp': ConvertString(obj.TitleNameJp(), password),
        'TitleNameTh': ConvertString(obj.TitleNameTh(), password),
        'TitleNameTw': ConvertString(obj.TitleNameTw(), password),
        'TitleNameEn': ConvertString(obj.TitleNameEn(), password),
        'TitleNameDe': ConvertString(obj.TitleNameDe(), password),
        'TitleNameFr': ConvertString(obj.TitleNameFr(), password),
        'SubTitleKr': ConvertString(obj.SubTitleKr(), password),
        'SubTitleJp': ConvertString(obj.SubTitleJp(), password),
        'SubTitleTh': ConvertString(obj.SubTitleTh(), password),
        'SubTitleTw': ConvertString(obj.SubTitleTw(), password),
        'SubTitleEn': ConvertString(obj.SubTitleEn(), password),
        'SubTitleDe': ConvertString(obj.SubTitleDe(), password),
        'SubTitleFr': ConvertString(obj.SubTitleFr(), password),
        'GachaDescriptionKr': ConvertString(obj.GachaDescriptionKr(), password),
        'GachaDescriptionJp': ConvertString(obj.GachaDescriptionJp(), password),
        'GachaDescriptionTh': ConvertString(obj.GachaDescriptionTh(), password),
        'GachaDescriptionTw': ConvertString(obj.GachaDescriptionTw(), password),
        'GachaDescriptionEn': ConvertString(obj.GachaDescriptionEn(), password),
        'GachaDescriptionDe': ConvertString(obj.GachaDescriptionDe(), password),
        'GachaDescriptionFr': ConvertString(obj.GachaDescriptionFr(), password),
    }

def dump_LocalizeInformationExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeOperatorExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizePrefabExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeScenarioExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'Kr': ConvertString(obj.Kr(), password),
        'Jp': ConvertString(obj.Jp(), password),
        'Th': ConvertString(obj.Th(), password),
        'Tw': ConvertString(obj.Tw(), password),
        'En': ConvertString(obj.En(), password),
        'De': ConvertString(obj.De(), password),
        'Fr': ConvertString(obj.Fr(), password),
    }

def dump_LocalizeSkillExcel(obj, password) -> dict:
    return {
        'Key': ConvertUInt(obj.Key(), password),
        'NameKr': ConvertString(obj.NameKr(), password),
        'DescriptionKr': ConvertString(obj.DescriptionKr(), password),
        'SkillInvokeLocalizeKr': ConvertString(obj.SkillInvokeLocalizeKr(), password),
        'NameJp': ConvertString(obj.NameJp(), password),
        'DescriptionJp': ConvertString(obj.DescriptionJp(), password),
        'SkillInvokeLocalizeJp': ConvertString(obj.SkillInvokeLocalizeJp(), password),
        'NameTh': ConvertString(obj.NameTh(), password),
        'DescriptionTh': ConvertString(obj.DescriptionTh(), password),
        'SkillInvokeLocalizeTh': ConvertString(obj.SkillInvokeLocalizeTh(), password),
        'NameTw': ConvertString(obj.NameTw(), password),
        'DescriptionTw': ConvertString(obj.DescriptionTw(), password),
        'SkillInvokeLocalizeTw': ConvertString(obj.SkillInvokeLocalizeTw(), password),
        'NameEn': ConvertString(obj.NameEn(), password),
        'DescriptionEn': ConvertString(obj.DescriptionEn(), password),
        'SkillInvokeLocalizeEn': ConvertString(obj.SkillInvokeLocalizeEn(), password),
        'NameDe': ConvertString(obj.NameDe(), password),
        'DescriptionDe': ConvertString(obj.DescriptionDe(), password),
        'SkillInvokeLocalizeDe': ConvertString(obj.SkillInvokeLocalizeDe(), password),
        'NameFr': ConvertString(obj.NameFr(), password),
        'DescriptionFr': ConvertString(obj.DescriptionFr(), password),
        'SkillInvokeLocalizeFr': ConvertString(obj.SkillInvokeLocalizeFr(), password),
    }

def dump_LogicEffectCommonVisualExcel(obj, password) -> dict:
    return {
        'StringID': ConvertUInt(obj.StringID(), password),
        'IconSpriteName': ConvertString(obj.IconSpriteName(), password),
        'IconDispelColor': [ConvertFloat(obj.IconDispelColor(j), password) for j in range(obj.IconDispelColorLength())],
        'ParticleEnterPath': ConvertString(obj.ParticleEnterPath(), password),
        'ParticleEnterSocket': EffectBone(ConvertInt(obj.ParticleEnterSocket(), password)).name,
        'ParticleLoopPath': ConvertString(obj.ParticleLoopPath(), password),
        'ParticleLoopSocket': EffectBone(ConvertInt(obj.ParticleLoopSocket(), password)).name,
        'ParticleEndPath': ConvertString(obj.ParticleEndPath(), password),
        'ParticleEndSocket': EffectBone(ConvertInt(obj.ParticleEndSocket(), password)).name,
        'ParticleApplyPath': ConvertString(obj.ParticleApplyPath(), password),
        'ParticleApplySocket': EffectBone(ConvertInt(obj.ParticleApplySocket(), password)).name,
        'ParticleRemovedPath': ConvertString(obj.ParticleRemovedPath(), password),
        'ParticleRemovedSocket': EffectBone(ConvertInt(obj.ParticleRemovedSocket(), password)).name,
    }

def dump_MemoryLobbyExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'PrefabName': ConvertString(obj.PrefabName(), password),
        'SlotTextureName': ConvertString(obj.SlotTextureName(), password),
        'RewardTextureName': ConvertString(obj.RewardTextureName(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'AudioClipJp': ConvertString(obj.AudioClipJp(), password),
        'AudioClipKr': ConvertString(obj.AudioClipKr(), password),
        'AudioClipTh': ConvertString(obj.AudioClipTh(), password),
        'AudioClipTw': ConvertString(obj.AudioClipTw(), password),
        'AudioClipEn': ConvertString(obj.AudioClipEn(), password),
        'AudioClipDe': ConvertString(obj.AudioClipDe(), password),
        'AudioClipFr': ConvertString(obj.AudioClipFr(), password),
    }

def dump_MessagePopupExcel(obj, password) -> dict:
    return {
        'StringId': ConvertUInt(obj.StringId(), password),
        'MessagePopupLayout_': MessagePopupLayout(ConvertInt(obj.MessagePopupLayout_(), password)).name,
        'OrderType': MessagePopupImagePositionType(ConvertInt(obj.OrderType(), password)).name,
        'Image': ConvertString(obj.Image(), password),
        'TitleText': ConvertUInt(obj.TitleText(), password),
        'MessageText': ConvertUInt(obj.MessageText(), password),
        'DisplayXButton': obj.DisplayXButton(),
        'Button': [MessagePopupButtonType(ConvertInt(obj.Button(j), password)).name for j in range(obj.ButtonLength())],
        'ButtonText': [ConvertUInt(obj.ButtonText(j), password) for j in range(obj.ButtonTextLength())],
        'ButtonCommand': [ConvertString(obj.ButtonCommand(j), password) for j in range(obj.ButtonCommandLength())],
        'ButtonParameter': [ConvertString(obj.ButtonParameter(j), password) for j in range(obj.ButtonParameterLength())],
    }

def dump_MiniGameMissionExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'GroupId': ConvertLong(obj.GroupId(), password),
        'GroupName': ConvertString(obj.GroupName(), password),
        'Category': MissionCategory(ConvertInt(obj.Category(), password)).name,
        'Description': ConvertString(obj.Description(), password),
        'ResetType': MissionResetType(ConvertInt(obj.ResetType(), password)).name,
        'ViewFlag': obj.ViewFlag(),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'PreMissionId': [ConvertLong(obj.PreMissionId(j), password) for j in range(obj.PreMissionIdLength())],
        'AccountType': AccountState(ConvertInt(obj.AccountType(), password)).name,
        'AccountLevel': ConvertLong(obj.AccountLevel(), password),
        'ShortcutUI': [ConvertString(obj.ShortcutUI(j), password) for j in range(obj.ShortcutUILength())],
        'CompleteConditionType': MissionCompleteConditionType(ConvertInt(obj.CompleteConditionType(), password)).name,
        'CompleteConditionCount': ConvertLong(obj.CompleteConditionCount(), password),
        'CompleteConditionParameter': [ConvertLong(obj.CompleteConditionParameter(j), password) for j in range(obj.CompleteConditionParameterLength())],
        'CompleteConditionParameterName': [ConvertString(obj.CompleteConditionParameterName(j), password) for j in range(obj.CompleteConditionParameterNameLength())],
        'RewardIcon': ConvertString(obj.RewardIcon(), password),
        'MissionRewardParcelType': [ParcelType(ConvertInt(obj.MissionRewardParcelType(j), password)).name for j in range(obj.MissionRewardParcelTypeLength())],
        'MissionRewardParcelId': [ConvertLong(obj.MissionRewardParcelId(j), password) for j in range(obj.MissionRewardParcelIdLength())],
        'MissionRewardAmount': [ConvertInt(obj.MissionRewardAmount(j), password) for j in range(obj.MissionRewardAmountLength())],
    }

def dump_MiniGamePlayGuideExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'DisplayOrder': ConvertInt(obj.DisplayOrder(), password),
        'GuideTitle': ConvertString(obj.GuideTitle(), password),
        'GuideImagePath': ConvertString(obj.GuideImagePath(), password),
        'GuideText': ConvertString(obj.GuideText(), password),
    }

def dump_MiniGameRhythmBgmExcel(obj, password) -> dict:
    return {
        'RhythmBgmId': ConvertLong(obj.RhythmBgmId(), password),
        'EventContentId': ConvertLong(obj.EventContentId(), password),
        'StageSelectImagePath': ConvertString(obj.StageSelectImagePath(), password),
        'Bpm': ConvertLong(obj.Bpm(), password),
        'Bgm': ConvertLong(obj.Bgm(), password),
        'BgmNameText': ConvertString(obj.BgmNameText(), password),
        'BgmComposerText': ConvertString(obj.BgmComposerText(), password),
        'BgmLength': ConvertInt(obj.BgmLength(), password),
    }

def dump_MiniGameRhythmExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'RhythmBgmId': ConvertLong(obj.RhythmBgmId(), password),
        'PresetId': ConvertLong(obj.PresetId(), password),
        'StageDifficulty': Difficulty(ConvertInt(obj.StageDifficulty(), password)).name,
        'IsSpecial': obj.IsSpecial(),
        'OpenStageScoreAmount': ConvertLong(obj.OpenStageScoreAmount(), password),
        'MaxHp': ConvertLong(obj.MaxHp(), password),
        'MissDamage': ConvertLong(obj.MissDamage(), password),
        'CriticalHPRestoreValue': ConvertLong(obj.CriticalHPRestoreValue(), password),
        'MaxScore': ConvertLong(obj.MaxScore(), password),
        'FeverScoreRate': ConvertLong(obj.FeverScoreRate(), password),
        'NoteScoreRate': ConvertLong(obj.NoteScoreRate(), password),
        'ComboScoreRate': ConvertLong(obj.ComboScoreRate(), password),
        'AttackScoreRate': ConvertLong(obj.AttackScoreRate(), password),
        'FeverCriticalRate': ConvertFloat(obj.FeverCriticalRate(), password),
        'FeverAttackRate': ConvertFloat(obj.FeverAttackRate(), password),
        'MaxHpScore': ConvertLong(obj.MaxHpScore(), password),
        'RhythmFileName': ConvertString(obj.RhythmFileName(), password),
        'ArtLevelSceneName': ConvertString(obj.ArtLevelSceneName(), password),
        'ComboImagePath': ConvertString(obj.ComboImagePath(), password),
    }

def dump_MiniGameRhythmPresetExcel(obj, password) -> dict:
    return {
        'PresetId': ConvertLong(obj.PresetId(), password),
        'CameraId': ConvertLong(obj.CameraId(), password),
        'PCSpawnPositionX': ConvertFloat(obj.PCSpawnPositionX(), password),
        'PCSpawnPositionY': ConvertFloat(obj.PCSpawnPositionY(), password),
        'DetectionLinePositionX': ConvertFloat(obj.DetectionLinePositionX(), password),
        'DetectionLinePositionY': ConvertFloat(obj.DetectionLinePositionY(), password),
        'Speed': ConvertFloat(obj.Speed(), password),
        'RhythmNoteObjectLeft': ConvertString(obj.RhythmNoteObjectLeft(), password),
        'RhythmNoteObjectRight': ConvertString(obj.RhythmNoteObjectRight(), password),
        'RhythmNoteObjectBoth': ConvertString(obj.RhythmNoteObjectBoth(), password),
        'JudgeValuesCritical': ConvertFloat(obj.JudgeValuesCritical(), password),
        'JudgeValuesAttack': ConvertFloat(obj.JudgeValuesAttack(), password),
    }

def dump_MissionExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Category': MissionCategory(ConvertInt(obj.Category(), password)).name,
        'Description': ConvertString(obj.Description(), password),
        'ResetType': MissionResetType(ConvertInt(obj.ResetType(), password)).name,
        'ViewFlag': obj.ViewFlag(),
        'StartDate': ConvertString(obj.StartDate(), password),
        'EndDate': ConvertString(obj.EndDate(), password),
        'EndDay': ConvertLong(obj.EndDay(), password),
        'StartableEndDate': ConvertString(obj.StartableEndDate(), password),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'PreMissionId': [ConvertLong(obj.PreMissionId(j), password) for j in range(obj.PreMissionIdLength())],
        'AccountType': AccountState(ConvertInt(obj.AccountType(), password)).name,
        'AccountLevel': ConvertLong(obj.AccountLevel(), password),
        'ShortcutUI': [ConvertString(obj.ShortcutUI(j), password) for j in range(obj.ShortcutUILength())],
        'CompleteConditionType': MissionCompleteConditionType(ConvertInt(obj.CompleteConditionType(), password)).name,
        'CompleteConditionCount': ConvertLong(obj.CompleteConditionCount(), password),
        'CompleteConditionParameter': [ConvertLong(obj.CompleteConditionParameter(j), password) for j in range(obj.CompleteConditionParameterLength())],
        'CompleteConditionParameterName': [ConvertString(obj.CompleteConditionParameterName(j), password) for j in range(obj.CompleteConditionParameterNameLength())],
        'RewardIcon': ConvertString(obj.RewardIcon(), password),
        'MissionRewardParcelType': [ParcelType(ConvertInt(obj.MissionRewardParcelType(j), password)).name for j in range(obj.MissionRewardParcelTypeLength())],
        'MissionRewardParcelId': [ConvertLong(obj.MissionRewardParcelId(j), password) for j in range(obj.MissionRewardParcelIdLength())],
        'MissionRewardAmount': [ConvertInt(obj.MissionRewardAmount(j), password) for j in range(obj.MissionRewardAmountLength())],
    }

def dump_NormalSkillTemplateExcel(obj, password) -> dict:
    return {
        'Index': ConvertLong(obj.Index(), password),
        'FirstCoolTime': ConvertFloat(obj.FirstCoolTime(), password),
        'CoolTime': ConvertFloat(obj.CoolTime(), password),
        'MultiAni': obj.MultiAni(),
    }

def dump_ObstacleExcel(obj, password) -> dict:
    return {
        'Index': ConvertLong(obj.Index(), password),
        'PrefabName': ConvertString(obj.PrefabName(), password),
        'JumpAble': obj.JumpAble(),
        'SubOffset': [ConvertFloat(obj.SubOffset(j), password) for j in range(obj.SubOffsetLength())],
        'X': ConvertFloat(obj.X(), password),
        'Z': ConvertFloat(obj.Z(), password),
        'Hp': ConvertLong(obj.Hp(), password),
        'MaxHp': ConvertLong(obj.MaxHp(), password),
        'BlockRate': ConvertInt(obj.BlockRate(), password),
        'EvasionRate': ConvertInt(obj.EvasionRate(), password),
        'DestroyType': ObstacleDestroyType(ConvertInt(obj.DestroyType(), password)).name,
        'Point1Offeset': [ConvertFloat(obj.Point1Offeset(j), password) for j in range(obj.Point1OffesetLength())],
        'EnemyPoint1Osset': [ConvertFloat(obj.EnemyPoint1Osset(j), password) for j in range(obj.EnemyPoint1OssetLength())],
        'Point2Offeset': [ConvertFloat(obj.Point2Offeset(j), password) for j in range(obj.Point2OffesetLength())],
        'EnemyPoint2Osset': [ConvertFloat(obj.EnemyPoint2Osset(j), password) for j in range(obj.EnemyPoint2OssetLength())],
        'SubObstacleID': [ConvertLong(obj.SubObstacleID(j), password) for j in range(obj.SubObstacleIDLength())],
    }

def dump_ObstacleFireLineCheckExcel(obj, password) -> dict:
    return {
        'MyObstacleFireLineCheck': obj.MyObstacleFireLineCheck(),
        'AllyObstacleFireLineCheck': obj.AllyObstacleFireLineCheck(),
        'EnemyObstacleFireLineCheck': obj.EnemyObstacleFireLineCheck(),
        'EmptyObstacleFireLineCheck': obj.EmptyObstacleFireLineCheck(),
    }

def dump_ObstacleStatExcel(obj, password) -> dict:
    return {
        'StringID': ConvertUInt(obj.StringID(), password),
        'Name': ConvertString(obj.Name(), password),
        'MaxHP1': ConvertLong(obj.MaxHP1(), password),
        'MaxHP100': ConvertLong(obj.MaxHP100(), password),
        'BlockRate': ConvertLong(obj.BlockRate(), password),
        'Dodge': ConvertLong(obj.Dodge(), password),
        'HighlightFloaterHeight': ConvertFloat(obj.HighlightFloaterHeight(), password),
    }

def dump_OpenConditionExcel(obj, password) -> dict:
    return {
        'OpenConditionContentType': OpenConditionContent(ConvertInt(obj.OpenConditionContentType(), password)).name,
        'LockUI': [ConvertString(obj.LockUI(j), password) for j in range(obj.LockUILength())],
        'ShortcutPopupPriority': ConvertLong(obj.ShortcutPopupPriority(), password),
        'ShortcutUIName': [ConvertString(obj.ShortcutUIName(j), password) for j in range(obj.ShortcutUINameLength())],
        'ShortcutParam': ConvertInt(obj.ShortcutParam(), password),
        'Scene': ConvertString(obj.Scene(), password),
        'HideWhenLocked': obj.HideWhenLocked(),
        'AccountLevel': ConvertLong(obj.AccountLevel(), password),
        'CampaignStageId': ConvertLong(obj.CampaignStageId(), password),
        'MultipleConditionCheckType_': MultipleConditionCheckType(ConvertInt(obj.MultipleConditionCheckType_(), password)).name,
        'OpenDayOfWeek': WeekDay(ConvertInt(obj.OpenDayOfWeek(), password)).name,
        'OpenHour': ConvertLong(obj.OpenHour(), password),
        'CloseDayOfWeek': WeekDay(ConvertInt(obj.CloseDayOfWeek(), password)).name,
        'CloseHour': ConvertLong(obj.CloseHour(), password),
        'CafeRank': ConvertLong(obj.CafeRank(), password),
    }

def dump_OperatorExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'GroupId': ConvertString(obj.GroupId(), password),
        'OperatorCondition_': OperatorCondition(ConvertInt(obj.OperatorCondition_(), password)).name,
        'OutputSequence': ConvertInt(obj.OutputSequence(), password),
        'RandomWeight': ConvertInt(obj.RandomWeight(), password),
        'OutputDelay': ConvertInt(obj.OutputDelay(), password),
        'Duration': ConvertInt(obj.Duration(), password),
        'PortraitPath': ConvertString(obj.PortraitPath(), password),
        'TextLocalizeKey': ConvertString(obj.TextLocalizeKey(), password),
        'VoiceClipsKr': [ConvertString(obj.VoiceClipsKr(j), password) for j in range(obj.VoiceClipsKrLength())],
        'VoiceClipsJp': [ConvertString(obj.VoiceClipsJp(j), password) for j in range(obj.VoiceClipsJpLength())],
        'VoiceClipsTh': [ConvertString(obj.VoiceClipsTh(j), password) for j in range(obj.VoiceClipsThLength())],
        'VoiceClipsTw': [ConvertString(obj.VoiceClipsTw(j), password) for j in range(obj.VoiceClipsTwLength())],
        'VoiceClipsEn': [ConvertString(obj.VoiceClipsEn(j), password) for j in range(obj.VoiceClipsEnLength())],
        'VoiceClipsDe': [ConvertString(obj.VoiceClipsDe(j), password) for j in range(obj.VoiceClipsDeLength())],
        'VoiceClipsFr': [ConvertString(obj.VoiceClipsFr(j), password) for j in range(obj.VoiceClipsFrLength())],
    }

def dump_PersonalityExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Name': ConvertString(obj.Name(), password),
    }

def dump_PickupDuplicateBonusExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ShopCategoryType_': ShopCategoryType(ConvertInt(obj.ShopCategoryType_(), password)).name,
        'ShopId': ConvertLong(obj.ShopId(), password),
        'PickupCharacterId': ConvertLong(obj.PickupCharacterId(), password),
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'RewardParcelAmount': ConvertLong(obj.RewardParcelAmount(), password),
    }

def dump_PresetCharactersExcel(obj, password) -> dict:
    return {
        'CharacterId': ConvertLong(obj.CharacterId(), password),
        'PresetGroupId': ConvertLong(obj.PresetGroupId(), password),
        'ArenaSimulatorFixed': obj.ArenaSimulatorFixed(),
        'Level': ConvertInt(obj.Level(), password),
        'Exp': ConvertInt(obj.Exp(), password),
        'FavorExp': ConvertInt(obj.FavorExp(), password),
        'FavorRank': ConvertInt(obj.FavorRank(), password),
        'StarGrade': ConvertInt(obj.StarGrade(), password),
        'ExSkillLevel': ConvertInt(obj.ExSkillLevel(), password),
        'PassiveSkillLevel': ConvertInt(obj.PassiveSkillLevel(), password),
        'ExtraPassiveSkillLevel': ConvertInt(obj.ExtraPassiveSkillLevel(), password),
        'CommonSkillLevel': ConvertInt(obj.CommonSkillLevel(), password),
        'LeaderSkillLevel': ConvertInt(obj.LeaderSkillLevel(), password),
        'EquipSlot01': obj.EquipSlot01(),
        'EquipSlotTier01': ConvertInt(obj.EquipSlotTier01(), password),
        'EquipSlotLevel01': ConvertInt(obj.EquipSlotLevel01(), password),
        'EquipSlot02': obj.EquipSlot02(),
        'EquipSlotTier02': ConvertInt(obj.EquipSlotTier02(), password),
        'EquipSlotLevel02': ConvertInt(obj.EquipSlotLevel02(), password),
        'EquipSlot03': obj.EquipSlot03(),
        'EquipSlotTier03': ConvertInt(obj.EquipSlotTier03(), password),
        'EquipSlotLevel03': ConvertInt(obj.EquipSlotLevel03(), password),
    }

def dump_PresetParcelsExcel(obj, password) -> dict:
    return {
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelId': ConvertLong(obj.ParcelId(), password),
        'PresetGroupId': ConvertLong(obj.PresetGroupId(), password),
        'ParcelAmount': ConvertLong(obj.ParcelAmount(), password),
    }

def dump_ProductExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ProductId': ConvertString(obj.ProductId(), password),
        'StoreType_': StoreType(ConvertInt(obj.StoreType_(), password)).name,
        'Price': ConvertLong(obj.Price(), password),
        'PriceReference': ConvertString(obj.PriceReference(), password),
        'PurchasePeriodType_': PurchasePeriodType(ConvertInt(obj.PurchasePeriodType_(), password)).name,
        'PurchasePeriodLimit': ConvertLong(obj.PurchasePeriodLimit(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ParcelAmount': [ConvertLong(obj.ParcelAmount(j), password) for j in range(obj.ParcelAmountLength())],
    }

def dump_ProductMonthlyExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'ProductId': ConvertString(obj.ProductId(), password),
        'StoreType_': StoreType(ConvertInt(obj.StoreType_(), password)).name,
        'Price': ConvertLong(obj.Price(), password),
        'PriceReference': ConvertString(obj.PriceReference(), password),
        'MonthlyDays': ConvertLong(obj.MonthlyDays(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ParcelAmount': [ConvertLong(obj.ParcelAmount(j), password) for j in range(obj.ParcelAmountLength())],
        'DailyParcelType': [ParcelType(ConvertInt(obj.DailyParcelType(j), password)).name for j in range(obj.DailyParcelTypeLength())],
        'DailyParcelId': [ConvertLong(obj.DailyParcelId(j), password) for j in range(obj.DailyParcelIdLength())],
        'DailyParcelAmount': [ConvertLong(obj.DailyParcelAmount(j), password) for j in range(obj.DailyParcelAmountLength())],
    }

def dump_ProtocolSettingExcel(obj, password) -> dict:
    return {
        'Protocol': ConvertString(obj.Protocol(), password),
        'ContentLockType_': ContentLockType(ConvertInt(obj.ContentLockType_(), password)).name,
        'OpenConditionContent_': OpenConditionContent(ConvertInt(obj.OpenConditionContent_(), password)).name,
        'Currency': obj.Currency(),
        'Inventory': obj.Inventory(),
        'Mail': obj.Mail(),
    }

def dump_RaidRankingRewardExcel(obj, password) -> dict:
    return {
        'RankingRewardGroupId': ConvertLong(obj.RankingRewardGroupId(), password),
        'Id': ConvertLong(obj.Id(), password),
        'RankStart': ConvertLong(obj.RankStart(), password),
        'RankEnd': ConvertLong(obj.RankEnd(), password),
        'RankStartTw': ConvertLong(obj.RankStartTw(), password),
        'RankEndTw': ConvertLong(obj.RankEndTw(), password),
        'RankStartAsia': ConvertLong(obj.RankStartAsia(), password),
        'RankEndAsia': ConvertLong(obj.RankEndAsia(), password),
        'RankStartNa': ConvertLong(obj.RankStartNa(), password),
        'RankEndNa': ConvertLong(obj.RankEndNa(), password),
        'RankStartGlobal': ConvertLong(obj.RankStartGlobal(), password),
        'RankEndGlobal': ConvertLong(obj.RankEndGlobal(), password),
        'PercentRankStart': ConvertLong(obj.PercentRankStart(), password),
        'PercentRankEnd': ConvertLong(obj.PercentRankEnd(), password),
        'Tier': ConvertInt(obj.Tier(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelUniqueId': [ConvertLong(obj.RewardParcelUniqueId(j), password) for j in range(obj.RewardParcelUniqueIdLength())],
        'RewardParcelUniqueName': [ConvertString(obj.RewardParcelUniqueName(j), password) for j in range(obj.RewardParcelUniqueNameLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_RaidSeasonManageExcel(obj, password) -> dict:
    return {
        'SeasonId': ConvertLong(obj.SeasonId(), password),
        'SeasonStartData': ConvertString(obj.SeasonStartData(), password),
        'SeasonEndData': ConvertString(obj.SeasonEndData(), password),
        'SettlementEndDate': ConvertString(obj.SettlementEndDate(), password),
        'OpenRaidBossGroup': [ConvertString(obj.OpenRaidBossGroup(j), password) for j in range(obj.OpenRaidBossGroupLength())],
        'RankingRewardGroupId': ConvertLong(obj.RankingRewardGroupId(), password),
        'MaxSeasonRewardGauage': ConvertInt(obj.MaxSeasonRewardGauage(), password),
        'StackedSeasonRewardGauge': [ConvertLong(obj.StackedSeasonRewardGauge(j), password) for j in range(obj.StackedSeasonRewardGaugeLength())],
        'SeasonRewardId': [ConvertLong(obj.SeasonRewardId(j), password) for j in range(obj.SeasonRewardIdLength())],
    }

def dump_RaidStageExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'UseBossIndex': obj.UseBossIndex(),
        'RaidBossGroup': ConvertString(obj.RaidBossGroup(), password),
        'PortraitPath': ConvertString(obj.PortraitPath(), password),
        'BGPath': ConvertString(obj.BGPath(), password),
        'RaidCharacterId': ConvertLong(obj.RaidCharacterId(), password),
        'BossCharacterId': [ConvertLong(obj.BossCharacterId(j), password) for j in range(obj.BossCharacterIdLength())],
        'Difficulty_': Difficulty(ConvertInt(obj.Difficulty_(), password)).name,
        'DifficultyOpenCondition': obj.DifficultyOpenCondition(),
        'MaxPlayerCount': ConvertLong(obj.MaxPlayerCount(), password),
        'StageCreateCostType': CurrencyTypes(ConvertInt(obj.StageCreateCostType(), password)).name,
        'StageCreateCostAmount': ConvertInt(obj.StageCreateCostAmount(), password),
        'StageEnterCostType': CurrencyTypes(ConvertInt(obj.StageEnterCostType(), password)).name,
        'StageEnterCostAmount': ConvertInt(obj.StageEnterCostAmount(), password),
        'RaidRoomLifeTime': ConvertInt(obj.RaidRoomLifeTime(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'GroundId': ConvertLong(obj.GroundId(), password),
        'GroundDevName': ConvertString(obj.GroundDevName(), password),
        'EnterTimeLine': ConvertString(obj.EnterTimeLine(), password),
        'TacticEnvironment_': TacticEnvironment(ConvertInt(obj.TacticEnvironment_(), password)).name,
        'SeasonDamageRatio': ConvertInt(obj.SeasonDamageRatio(), password),
        'DefaultClearScore': ConvertLong(obj.DefaultClearScore(), password),
        'MaximumScore': ConvertLong(obj.MaximumScore(), password),
        'PerSecondMinusScore': ConvertLong(obj.PerSecondMinusScore(), password),
        'HPPercentScore': ConvertLong(obj.HPPercentScore(), password),
        'RaidRewardGroupId': ConvertLong(obj.RaidRewardGroupId(), password),
        'RaidRewardDevName': ConvertString(obj.RaidRewardDevName(), password),
        'BattleReadyTimelinePath': [ConvertString(obj.BattleReadyTimelinePath(j), password) for j in range(obj.BattleReadyTimelinePathLength())],
        'BattleReadyTimelinePhaseStart': [ConvertInt(obj.BattleReadyTimelinePhaseStart(j), password) for j in range(obj.BattleReadyTimelinePhaseStartLength())],
        'BattleReadyTimelinePhaseEnd': [ConvertInt(obj.BattleReadyTimelinePhaseEnd(j), password) for j in range(obj.BattleReadyTimelinePhaseEndLength())],
        'VictoryTimelinePath': ConvertString(obj.VictoryTimelinePath(), password),
        'PhaseChangeTimelinePath': ConvertString(obj.PhaseChangeTimelinePath(), password),
        'TimeLinePhase': ConvertLong(obj.TimeLinePhase(), password),
        'EnterScenarioKey': ConvertUInt(obj.EnterScenarioKey(), password),
        'ClearScenarioKey': ConvertUInt(obj.ClearScenarioKey(), password),
        'ReviveParcelType': ParcelType(ConvertInt(obj.ReviveParcelType(), password)).name,
        'ReviveParcelId': ConvertLong(obj.ReviveParcelId(), password),
        'ReviveParcelDevName': ConvertString(obj.ReviveParcelDevName(), password),
        'ReviveParcelAmount': ConvertLong(obj.ReviveParcelAmount(), password),
        'InitSupplyCount': ConvertInt(obj.InitSupplyCount(), password),
        'ShowSkillCard': obj.ShowSkillCard(),
        'BossBGInfoKey': ConvertUInt(obj.BossBGInfoKey(), password),
    }

def dump_RaidStageRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'IsClearStageRewardHideInfo': obj.IsClearStageRewardHideInfo(),
        'ClearStageRewardProb': ConvertLong(obj.ClearStageRewardProb(), password),
        'ClearStageRewardParcelType': ParcelType(ConvertInt(obj.ClearStageRewardParcelType(), password)).name,
        'ClearStageRewardParcelUniqueID': ConvertLong(obj.ClearStageRewardParcelUniqueID(), password),
        'ClearStageRewardParcelUniqueName': ConvertString(obj.ClearStageRewardParcelUniqueName(), password),
        'ClearStageRewardAmount': ConvertLong(obj.ClearStageRewardAmount(), password),
    }

def dump_RaidStageSeasonRewardExcel(obj, password) -> dict:
    return {
        'SeasonRewardId': ConvertLong(obj.SeasonRewardId(), password),
        'SeasonRewardParcelType': [ParcelType(ConvertInt(obj.SeasonRewardParcelType(j), password)).name for j in range(obj.SeasonRewardParcelTypeLength())],
        'SeasonRewardParcelUniqueId': [ConvertLong(obj.SeasonRewardParcelUniqueId(j), password) for j in range(obj.SeasonRewardParcelUniqueIdLength())],
        'SeasonRewardParcelUniqueName': [ConvertString(obj.SeasonRewardParcelUniqueName(j), password) for j in range(obj.SeasonRewardParcelUniqueNameLength())],
        'SeasonRewardAmount': [ConvertLong(obj.SeasonRewardAmount(j), password) for j in range(obj.SeasonRewardAmountLength())],
    }

def dump_RecipeCraftExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'RecipeType_': RecipeType(ConvertInt(obj.RecipeType_(), password)).name,
        'RecipeIngredientId': ConvertLong(obj.RecipeIngredientId(), password),
        'RecipeIngredientDevName': ConvertString(obj.RecipeIngredientDevName(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ParcelDevName': [ConvertString(obj.ParcelDevName(j), password) for j in range(obj.ParcelDevNameLength())],
        'ResultAmountMin': [ConvertLong(obj.ResultAmountMin(j), password) for j in range(obj.ResultAmountMinLength())],
        'ResultAmountMax': [ConvertLong(obj.ResultAmountMax(j), password) for j in range(obj.ResultAmountMaxLength())],
    }

def dump_RecipeExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'RecipeType_': RecipeType(ConvertInt(obj.RecipeType_(), password)).name,
        'RecipeIngredientId': ConvertLong(obj.RecipeIngredientId(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ResultAmountMin': [ConvertLong(obj.ResultAmountMin(j), password) for j in range(obj.ResultAmountMinLength())],
        'ResultAmountMax': [ConvertLong(obj.ResultAmountMax(j), password) for j in range(obj.ResultAmountMaxLength())],
    }

def dump_RecipeIngredientExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'RecipeType_': RecipeType(ConvertInt(obj.RecipeType_(), password)).name,
        'CostParcelType': [ParcelType(ConvertInt(obj.CostParcelType(j), password)).name for j in range(obj.CostParcelTypeLength())],
        'CostId': [ConvertLong(obj.CostId(j), password) for j in range(obj.CostIdLength())],
        'CostAmount': [ConvertLong(obj.CostAmount(j), password) for j in range(obj.CostAmountLength())],
        'IngredientParcelType': [ParcelType(ConvertInt(obj.IngredientParcelType(j), password)).name for j in range(obj.IngredientParcelTypeLength())],
        'IngredientId': [ConvertLong(obj.IngredientId(j), password) for j in range(obj.IngredientIdLength())],
        'IngredientAmount': [ConvertLong(obj.IngredientAmount(j), password) for j in range(obj.IngredientAmountLength())],
        'CostTimeInSecond': ConvertLong(obj.CostTimeInSecond(), password),
    }

def dump_Position(obj, password) -> dict:
    return {
        'X': ConvertFloat(obj.X(), password),
        'Z': ConvertFloat(obj.Z(), password),
    }

def dump_Motion(obj, password) -> dict:
    return {
        'Name': ConvertString(obj.Name(), password),
        'Positions': [dump_Position(obj.Positions(j), password) for j in range(obj.PositionsLength())],
    }

def dump_MoveEnd(obj, password) -> dict:
    return {
        'Normal': dump_Motion(obj.Normal(), password),
        'Stand': dump_Motion(obj.Stand(), password),
        'Kneel': dump_Motion(obj.Kneel(), password),
    }

def dump_Form(obj, password) -> dict:
    return {
        'MoveEnd_': dump_MoveEnd(obj.MoveEnd_(), password),
        'PublicSkill': dump_Motion(obj.PublicSkill(), password),
    }

def dump_RootMotionFlat(obj, password) -> dict:
    return {
        'Forms': [dump_Form(obj.Forms(j), password) for j in range(obj.FormsLength())],
        'ExSkills': [dump_Motion(obj.ExSkills(j), password) for j in range(obj.ExSkillsLength())],
        'MoveLeft': dump_Motion(obj.MoveLeft(), password),
        'MoveRight': dump_Motion(obj.MoveRight(), password),
    }

def dump_ScenarioBGEffectExcel(obj, password) -> dict:
    return {
        'Name': ConvertUInt(obj.Name(), password),
        'Effect': ConvertString(obj.Effect(), password),
        'Scroll': ScenarioBGScroll(ConvertInt(obj.Scroll(), password)).name,
        'ScrollTime': ConvertLong(obj.ScrollTime(), password),
        'ScrollFrom': ConvertLong(obj.ScrollFrom(), password),
        'ScrollTo': ConvertLong(obj.ScrollTo(), password),
    }

def dump_ScenarioBGNameExcel(obj, password) -> dict:
    return {
        'Name': ConvertUInt(obj.Name(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'BGFileName': ConvertString(obj.BGFileName(), password),
        'BGType': ScenarioBGType(ConvertInt(obj.BGType(), password)).name,
        'AnimationRoot': ConvertString(obj.AnimationRoot(), password),
        'AnimationName': ConvertString(obj.AnimationName(), password),
        'SpineScale': ConvertFloat(obj.SpineScale(), password),
        'SpineLocalPosX': ConvertInt(obj.SpineLocalPosX(), password),
        'SpineLocalPosY': ConvertInt(obj.SpineLocalPosY(), password),
    }

def dump_ScenarioBGName_GlobalExcel(obj, password) -> dict:
    return {
        'GroupName': ConvertUInt(obj.GroupName(), password),
        'NameKr': ConvertUInt(obj.NameKr(), password),
        'NameTw': ConvertUInt(obj.NameTw(), password),
        'NameAsia': ConvertUInt(obj.NameAsia(), password),
        'NameNa': ConvertUInt(obj.NameNa(), password),
        'NameGlobal': ConvertUInt(obj.NameGlobal(), password),
    }

def dump_ScenarioCharacterEmotionExcel(obj, password) -> dict:
    return {
        'EmoticonName': ConvertString(obj.EmoticonName(), password),
        'Name': ConvertUInt(obj.Name(), password),
    }

def dump_ScenarioCharacterNameExcel(obj, password) -> dict:
    return {
        'CharacterName': ConvertUInt(obj.CharacterName(), password),
        'ProductionStep_': ProductionStep(ConvertInt(obj.ProductionStep_(), password)).name,
        'NameKR': ConvertString(obj.NameKR(), password),
        'NicknameKR': ConvertString(obj.NicknameKR(), password),
        'NameJP': ConvertString(obj.NameJP(), password),
        'NicknameJP': ConvertString(obj.NicknameJP(), password),
        'NameTH': ConvertString(obj.NameTH(), password),
        'NicknameTH': ConvertString(obj.NicknameTH(), password),
        'NameTW': ConvertString(obj.NameTW(), password),
        'NicknameTW': ConvertString(obj.NicknameTW(), password),
        'NameEN': ConvertString(obj.NameEN(), password),
        'NicknameEN': ConvertString(obj.NicknameEN(), password),
        'NameDE': ConvertString(obj.NameDE(), password),
        'NicknameDE': ConvertString(obj.NicknameDE(), password),
        'NameFR': ConvertString(obj.NameFR(), password),
        'NicknameFR': ConvertString(obj.NicknameFR(), password),
        'Shape': ScenarioCharacterShapes(ConvertInt(obj.Shape(), password)).name,
        'SpinePrefabName': ConvertString(obj.SpinePrefabName(), password),
        'SmallPortrait': ConvertString(obj.SmallPortrait(), password),
    }

def dump_ScenarioCharacterSituationSetExcel(obj, password) -> dict:
    return {
        'Name': ConvertUInt(obj.Name(), password),
        'Face': ConvertString(obj.Face(), password),
        'Behavior': ConvertString(obj.Behavior(), password),
        'Action': ConvertString(obj.Action(), password),
        'Shape': ConvertString(obj.Shape(), password),
        'Effect': ConvertUInt(obj.Effect(), password),
        'Emotion': ConvertUInt(obj.Emotion(), password),
    }

def dump_ScenarioEffectExcel(obj, password) -> dict:
    return {
        'EffectName': ConvertString(obj.EffectName(), password),
        'Name': ConvertUInt(obj.Name(), password),
    }

def dump_ScenarioModeExcel(obj, password) -> dict:
    return {
        'ModeId': ConvertLong(obj.ModeId(), password),
        'ModeType': ScenarioModeTypes(ConvertInt(obj.ModeType(), password)).name,
        'SubType': ScenarioModeSubTypes(ConvertInt(obj.SubType(), password)).name,
        'VolumeId': ConvertLong(obj.VolumeId(), password),
        'ChapterId': ConvertLong(obj.ChapterId(), password),
        'EpisodeId': ConvertLong(obj.EpisodeId(), password),
        'Hide': obj.Hide(),
        'Open': obj.Open(),
        'FrontScenarioGroupId': [ConvertLong(obj.FrontScenarioGroupId(j), password) for j in range(obj.FrontScenarioGroupIdLength())],
        'GroundId': ConvertLong(obj.GroundId(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'BackScenarioGroupId': [ConvertLong(obj.BackScenarioGroupId(j), password) for j in range(obj.BackScenarioGroupIdLength())],
        'ClearedModeId': ConvertLong(obj.ClearedModeId(), password),
        'AccountLevelLimit': ConvertLong(obj.AccountLevelLimit(), password),
        'ClearedStageId': ConvertLong(obj.ClearedStageId(), password),
        'NeedClub': Club(ConvertInt(obj.NeedClub(), password)).name,
        'NeedClubStudentCount': ConvertInt(obj.NeedClubStudentCount(), password),
        'NeedTSS': ConvertLong(obj.NeedTSS(), password),
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'FixedEchelonId': ConvertLong(obj.FixedEchelonId(), password),
        'CompleteReportEventName': ConvertString(obj.CompleteReportEventName(), password),
    }

def dump_ScenarioModeRewardExcel(obj, password) -> dict:
    return {
        'ModeId': ConvertLong(obj.ModeId(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardParcelAmount': [ConvertInt(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
    }

def dump_ScenarioReplayExcel(obj, password) -> dict:
    return {
        'ModeId': ConvertLong(obj.ModeId(), password),
        'VolumeId': ConvertLong(obj.VolumeId(), password),
        'ReplayType': ScenarioModeReplayTypes(ConvertInt(obj.ReplayType(), password)).name,
        'ChapterId': ConvertLong(obj.ChapterId(), password),
        'EpisodeId': ConvertLong(obj.EpisodeId(), password),
        'FrontScenarioGroupId': [ConvertLong(obj.FrontScenarioGroupId(j), password) for j in range(obj.FrontScenarioGroupIdLength())],
        'GroundId': ConvertLong(obj.GroundId(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'BackScenarioGroupId': [ConvertLong(obj.BackScenarioGroupId(j), password) for j in range(obj.BackScenarioGroupIdLength())],
    }

def dump_ScenarioScriptContentExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptEvent1Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptEvent2Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptEvent3Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptFavor1Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptFavor2Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptFavor3Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptGroup1Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptGroup2Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptGroup3Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptMain1Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptMain2Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptMain3Excel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioScriptTestExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'SelectionGroup': ConvertLong(obj.SelectionGroup(), password),
        'BGMId': ConvertLong(obj.BGMId(), password),
        'Sound': ConvertString(obj.Sound(), password),
        'Transition': ConvertUInt(obj.Transition(), password),
        'BGName': ConvertUInt(obj.BGName(), password),
        'BGEffect': ConvertUInt(obj.BGEffect(), password),
        'PopupFileName': ConvertString(obj.PopupFileName(), password),
        'ScriptKr': ConvertString(obj.ScriptKr(), password),
        'TextJp': ConvertString(obj.TextJp(), password),
        'TextTh': ConvertString(obj.TextTh(), password),
        'TextTw': ConvertString(obj.TextTw(), password),
        'TextEn': ConvertString(obj.TextEn(), password),
        'TextDe': ConvertString(obj.TextDe(), password),
        'TextFr': ConvertString(obj.TextFr(), password),
        'VoiceJp': ConvertString(obj.VoiceJp(), password),
    }

def dump_ScenarioTransitionExcel(obj, password) -> dict:
    return {
        'Name': ConvertUInt(obj.Name(), password),
        'TransitionOut': ConvertString(obj.TransitionOut(), password),
        'TransitionOutDuration': ConvertLong(obj.TransitionOutDuration(), password),
        'TransitionOutResource': ConvertString(obj.TransitionOutResource(), password),
        'TransitionIn': ConvertString(obj.TransitionIn(), password),
        'TransitionInDuration': ConvertLong(obj.TransitionInDuration(), password),
        'TransitionInResource': ConvertString(obj.TransitionInResource(), password),
    }

def dump_SchoolDungeonRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'DungeonType': SchoolDungeonType(ConvertInt(obj.DungeonType(), password)).name,
        'RewardTag_': RewardTag(ConvertInt(obj.RewardTag_(), password)).name,
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'RewardParcelAmount': ConvertLong(obj.RewardParcelAmount(), password),
        'RewardParcelProbability': ConvertLong(obj.RewardParcelProbability(), password),
        'IsDisplayed': obj.IsDisplayed(),
    }

def dump_SchoolDungeonStageExcel(obj, password) -> dict:
    return {
        'StageId': ConvertLong(obj.StageId(), password),
        'DungeonType': SchoolDungeonType(ConvertInt(obj.DungeonType(), password)).name,
        'Difficulty': ConvertInt(obj.Difficulty(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'PrevStageId': ConvertLong(obj.PrevStageId(), password),
        'StageActionPointCostAmount': ConvertLong(obj.StageActionPointCostAmount(), password),
        'EnterCostType': CurrencyTypes(ConvertInt(obj.EnterCostType(), password)).name,
        'EnterCostAmount': ConvertLong(obj.EnterCostAmount(), password),
        'GroundId': ConvertInt(obj.GroundId(), password),
        'StarGoal': [WeekDungeonStarGoalType(ConvertInt(obj.StarGoal(j), password)).name for j in range(obj.StarGoalLength())],
        'StarGoalAmount': [ConvertInt(obj.StarGoalAmount(j), password) for j in range(obj.StarGoalAmountLength())],
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'RecommandLevel': ConvertLong(obj.RecommandLevel(), password),
        'StageRewardId': ConvertLong(obj.StageRewardId(), password),
        'PlayTimeLimitInSeconds': ConvertLong(obj.PlayTimeLimitInSeconds(), password),
    }

def dump_ServiceActionExcel(obj, password) -> dict:
    return {
        'ServiceActionType_': ServiceActionType(ConvertInt(obj.ServiceActionType_(), password)).name,
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': ConvertLong(obj.GoodsId(), password),
    }

def dump_ShopCashExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'CashProductId': ConvertLong(obj.CashProductId(), password),
        'PackageType': PurchaseSourceType(ConvertInt(obj.PackageType(), password)).name,
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'IconPath': ConvertString(obj.IconPath(), password),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'CategoryType': ProductCategory(ConvertInt(obj.CategoryType(), password)).name,
        'DisplayTag': ProductDisplayTag(ConvertInt(obj.DisplayTag(), password)).name,
        'SalePeriodFrom': ConvertString(obj.SalePeriodFrom(), password),
        'SalePeriodTo': ConvertString(obj.SalePeriodTo(), password),
        'PeriodTag': obj.PeriodTag(),
        'AccountLevelLimit': ConvertLong(obj.AccountLevelLimit(), password),
        'AccountLevelHide': obj.AccountLevelHide(),
        'ClearMissionLimit': ConvertLong(obj.ClearMissionLimit(), password),
        'ClearMissionHide': obj.ClearMissionHide(),
        'PurchaseReportEventName': ConvertString(obj.PurchaseReportEventName(), password),
        'PackageClientType': PurchaseSourceType(ConvertInt(obj.PackageClientType(), password)).name,
    }

def dump_ShopExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'SalePeriodFrom': ConvertString(obj.SalePeriodFrom(), password),
        'SalePeriodTo': ConvertString(obj.SalePeriodTo(), password),
        'PurchaseCooltimeMin': ConvertLong(obj.PurchaseCooltimeMin(), password),
        'PurchaseCountLimit': ConvertLong(obj.PurchaseCountLimit(), password),
        'PurchaseCountResetType_': PurchaseCountResetType(ConvertInt(obj.PurchaseCountResetType_(), password)).name,
        'BuyReportEventName': ConvertString(obj.BuyReportEventName(), password),
    }

def dump_ShopInfoExcel(obj, password) -> dict:
    return {
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'IsRefresh': obj.IsRefresh(),
        'ParcelType_': ParcelType(ConvertInt(obj.ParcelType_(), password)).name,
        'ParcelId': ConvertLong(obj.ParcelId(), password),
        'AutoRefreshCoolTime': ConvertLong(obj.AutoRefreshCoolTime(), password),
        'RefreshAbleCount': ConvertLong(obj.RefreshAbleCount(), password),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'OpenPeriodFrom': ConvertString(obj.OpenPeriodFrom(), password),
        'OpenPeriodTo': ConvertString(obj.OpenPeriodTo(), password),
    }

def dump_ShopRecruitExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': [ConvertLong(obj.GoodsId(j), password) for j in range(obj.GoodsIdLength())],
        'GoodsDevName': ConvertString(obj.GoodsDevName(), password),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'MovieBannerPath': [ConvertString(obj.MovieBannerPath(j), password) for j in range(obj.MovieBannerPathLength())],
        'LinkedRobbyBannerId': ConvertLong(obj.LinkedRobbyBannerId(), password),
        'InfoCharacterId': [ConvertLong(obj.InfoCharacterId(j), password) for j in range(obj.InfoCharacterIdLength())],
        'SalePeriodFrom': ConvertString(obj.SalePeriodFrom(), password),
        'SalePeriodTo': ConvertString(obj.SalePeriodTo(), password),
        'RecruitCoinId': ConvertLong(obj.RecruitCoinId(), password),
        'RecruitSellectionShopId': ConvertLong(obj.RecruitSellectionShopId(), password),
        'PurchaseCooltimeMin': ConvertLong(obj.PurchaseCooltimeMin(), password),
        'PurchaseCountLimit': ConvertLong(obj.PurchaseCountLimit(), password),
        'PurchaseCountResetType_': PurchaseCountResetType(ConvertInt(obj.PurchaseCountResetType_(), password)).name,
        'ProbabilityUrlDev': ConvertString(obj.ProbabilityUrlDev(), password),
        'ProbabilityUrlLive': ConvertString(obj.ProbabilityUrlLive(), password),
    }

def dump_ShopRefreshExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
        'IsLegacy': obj.IsLegacy(),
        'GoodsId': ConvertLong(obj.GoodsId(), password),
        'DisplayOrder': ConvertLong(obj.DisplayOrder(), password),
        'CategoryType': ShopCategoryType(ConvertInt(obj.CategoryType(), password)).name,
        'RefreshGroup': ConvertInt(obj.RefreshGroup(), password),
        'Prob': ConvertInt(obj.Prob(), password),
        'BuyReportEventName': ConvertString(obj.BuyReportEventName(), password),
    }

def dump_ShortcutTypeExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'IsAscending': obj.IsAscending(),
        'ContentType': [ShortcutContentType(ConvertInt(obj.ContentType(j), password)).name for j in range(obj.ContentTypeLength())],
    }

def dump_SkillExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'LocalizeSkillId': ConvertUInt(obj.LocalizeSkillId(), password),
        'GroupId': ConvertString(obj.GroupId(), password),
        'Level': ConvertInt(obj.Level(), password),
        'SkillCost': ConvertInt(obj.SkillCost(), password),
        'EnemySkillCost': ConvertInt(obj.EnemySkillCost(), password),
        'BulletType_': BulletType(ConvertInt(obj.BulletType_(), password)).name,
        'StartCoolTime': ConvertInt(obj.StartCoolTime(), password),
        'CoolTime': ConvertInt(obj.CoolTime(), password),
        'EnemyStartCoolTime': ConvertInt(obj.EnemyStartCoolTime(), password),
        'EnemyCoolTime': ConvertInt(obj.EnemyCoolTime(), password),
        'UseAtg': ConvertInt(obj.UseAtg(), password),
        'RequireCharacterLevel': ConvertInt(obj.RequireCharacterLevel(), password),
        'RequireLevelUpMaterial': ConvertLong(obj.RequireLevelUpMaterial(), password),
        'IconName': ConvertString(obj.IconName(), password),
        'IsShowInfo': obj.IsShowInfo(),
    }

def dump_SoundUIExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'SoundUniqueId': ConvertString(obj.SoundUniqueId(), password),
        'Path': ConvertString(obj.Path(), password),
    }

def dump_SpecialLobbyIllustExcel(obj, password) -> dict:
    return {
        'UniqueId': ConvertLong(obj.UniqueId(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'CharacterCostumeUniqueId': ConvertLong(obj.CharacterCostumeUniqueId(), password),
        'PrefabName': ConvertString(obj.PrefabName(), password),
        'SlotTextureName': ConvertString(obj.SlotTextureName(), password),
        'RewardTextureName': ConvertString(obj.RewardTextureName(), password),
    }

def dump_StatLevelInterpolationExcel(obj, password) -> dict:
    return {
        'Level': ConvertLong(obj.Level(), password),
        'Standard': ConvertLong(obj.Standard(), password),
        'Premature': ConvertLong(obj.Premature(), password),
        'LateBloom': ConvertLong(obj.LateBloom(), password),
        'Obstacle': ConvertLong(obj.Obstacle(), password),
    }

def dump_StrategyObjectBuffDefineExcel(obj, password) -> dict:
    return {
        'StrategyObjectBuffID': ConvertLong(obj.StrategyObjectBuffID(), password),
        'StrategyObjectTurn': ConvertInt(obj.StrategyObjectTurn(), password),
        'SkillGroupId': ConvertString(obj.SkillGroupId(), password),
        'LocalizeCodeId': ConvertUInt(obj.LocalizeCodeId(), password),
        'IconPath': ConvertString(obj.IconPath(), password),
    }

def dump_StringTestExcel(obj, password) -> dict:
    return {
        'String': [ConvertString(obj.String(j), password) for j in range(obj.StringLength())],
        'Sentence1': ConvertString(obj.Sentence1(), password),
        'Script': ConvertString(obj.Script(), password),
    }

def dump_SystemMailExcel(obj, password) -> dict:
    return {
        'MailType_': MailType(ConvertInt(obj.MailType_(), password)).name,
        'ExpiredDay': ConvertLong(obj.ExpiredDay(), password),
        'Sender': ConvertString(obj.Sender(), password),
        'Comment': ConvertString(obj.Comment(), password),
    }

def dump_TacticArenaSimulatorSettingExcel(obj, password) -> dict:
    return {
        'Order': ConvertLong(obj.Order(), password),
        'Repeat': ConvertLong(obj.Repeat(), password),
        'AttackerFrom': ArenaSimulatorServer(ConvertInt(obj.AttackerFrom(), password)).name,
        'AttackerUserArenaGroup': ConvertLong(obj.AttackerUserArenaGroup(), password),
        'AttackerUserArenaRank': ConvertLong(obj.AttackerUserArenaRank(), password),
        'AttackerPresetGroupId': ConvertLong(obj.AttackerPresetGroupId(), password),
        'AttackerStrikerNum': ConvertLong(obj.AttackerStrikerNum(), password),
        'AttackerSpecialNum': ConvertLong(obj.AttackerSpecialNum(), password),
        'DefenderFrom': ArenaSimulatorServer(ConvertInt(obj.DefenderFrom(), password)).name,
        'DefenderUserArenaGroup': ConvertLong(obj.DefenderUserArenaGroup(), password),
        'DefenderUserArenaRank': ConvertLong(obj.DefenderUserArenaRank(), password),
        'DefenderPresetGroupId': ConvertLong(obj.DefenderPresetGroupId(), password),
        'DefenderStrikerNum': ConvertLong(obj.DefenderStrikerNum(), password),
        'DefenderSpecialNum': ConvertLong(obj.DefenderSpecialNum(), password),
        'GroundId': ConvertLong(obj.GroundId(), password),
    }

def dump_TacticEntityEffectFilterExcel(obj, password) -> dict:
    return {
        'TargetEffectName': ConvertString(obj.TargetEffectName(), password),
        'ShowEffectToVehicle': obj.ShowEffectToVehicle(),
        'ShowEffectToBoss': obj.ShowEffectToBoss(),
    }

def dump_TacticSimulatorSettingExcel(obj, password) -> dict:
    return {
        'GroundId': ConvertLong(obj.GroundId(), password),
        'GetExp': ConvertLong(obj.GetExp(), password),
        'GetStarGrade': ConvertLong(obj.GetStarGrade(), password),
        'Equipment': ConvertLong(obj.Equipment(), password),
    }

def dump_TacticalSupportSystemExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'SummonedTime': ConvertLong(obj.SummonedTime(), password),
        'DefaultPersonalityId': ConvertLong(obj.DefaultPersonalityId(), password),
        'CanTargeting': obj.CanTargeting(),
        'CanCover': obj.CanCover(),
        'ObstacleUniqueName': ConvertString(obj.ObstacleUniqueName(), password),
        'ObstacleCoverRange': ConvertLong(obj.ObstacleCoverRange(), password),
        'SummonSkilllGroupId': ConvertString(obj.SummonSkilllGroupId(), password),
        'CrashObstacleOBBWidth': ConvertLong(obj.CrashObstacleOBBWidth(), password),
        'CrashObstacleOBBHeight': ConvertLong(obj.CrashObstacleOBBHeight(), password),
        'IsTSSBlockedNodeCheck': obj.IsTSSBlockedNodeCheck(),
        'NumberOfUses': ConvertInt(obj.NumberOfUses(), password),
        'InventoryOffsetX': ConvertFloat(obj.InventoryOffsetX(), password),
        'InventoryOffsetY': ConvertFloat(obj.InventoryOffsetY(), password),
        'InventoryOffsetZ': ConvertFloat(obj.InventoryOffsetZ(), password),
        'InteractionChar': [ConvertLong(obj.InteractionChar(j), password) for j in range(obj.InteractionCharLength())],
        'CharacterInteractionStartDelay': ConvertLong(obj.CharacterInteractionStartDelay(), password),
        'GetOnStartEffectPath': ConvertString(obj.GetOnStartEffectPath(), password),
        'GetOnEndEffectPath': ConvertString(obj.GetOnEndEffectPath(), password),
    }

def dump_TagSettingExcel(obj, password) -> dict:
    return {
        'Id': Tag(ConvertInt(obj.Id(), password)).name,
        'IsOpen': obj.IsOpen(),
        'LocalizeEtcId': ConvertUInt(obj.LocalizeEtcId(), password),
    }

def dump_TerrainAdaptationFactorExcel(obj, password) -> dict:
    return {
        'TerrainAdaptation': StageTopography(ConvertInt(obj.TerrainAdaptation(), password)).name,
        'TerrainAdaptationStat_': TerrainAdaptationStat(ConvertInt(obj.TerrainAdaptationStat_(), password)).name,
        'ShotFactor': ConvertLong(obj.ShotFactor(), password),
        'BlockFactor': ConvertLong(obj.BlockFactor(), password),
        'AccuracyFactor': ConvertLong(obj.AccuracyFactor(), password),
        'DodgeFactor': ConvertLong(obj.DodgeFactor(), password),
        'AttackPowerFactor': ConvertLong(obj.AttackPowerFactor(), password),
    }

def dump_ToastExcel(obj, password) -> dict:
    return {
        'Id': ConvertUInt(obj.Id(), password),
        'ToastType_': ToastType(ConvertInt(obj.ToastType_(), password)).name,
        'MissionId': ConvertUInt(obj.MissionId(), password),
        'TextId': ConvertUInt(obj.TextId(), password),
        'LifeTime': ConvertLong(obj.LifeTime(), password),
    }

def dump_TranscendenceRecipeExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'CostCurrencyType': CurrencyTypes(ConvertInt(obj.CostCurrencyType(), password)).name,
        'CostCurrencyAmount': ConvertLong(obj.CostCurrencyAmount(), password),
        'ParcelType_': [ParcelType(ConvertInt(obj.ParcelType_(j), password)).name for j in range(obj.ParcelType_Length())],
        'ParcelId': [ConvertLong(obj.ParcelId(j), password) for j in range(obj.ParcelIdLength())],
        'ParcelAmount': [ConvertInt(obj.ParcelAmount(j), password) for j in range(obj.ParcelAmountLength())],
    }

def dump_TutorialCharacterDialogExcel(obj, password) -> dict:
    return {
        'TalkId': ConvertLong(obj.TalkId(), password),
        'AnimationName': ConvertString(obj.AnimationName(), password),
        'LocalizeKR': ConvertString(obj.LocalizeKR(), password),
        'LocalizeJP': ConvertString(obj.LocalizeJP(), password),
        'LocalizeTH': ConvertString(obj.LocalizeTH(), password),
        'LocalizeTW': ConvertString(obj.LocalizeTW(), password),
        'LocalizeEN': ConvertString(obj.LocalizeEN(), password),
        'LocalizeDE': ConvertString(obj.LocalizeDE(), password),
        'LocalizeFR': ConvertString(obj.LocalizeFR(), password),
        'SoundPathKR': ConvertString(obj.SoundPathKR(), password),
        'SoundPathJP': ConvertString(obj.SoundPathJP(), password),
        'SoundPathTH': ConvertString(obj.SoundPathTH(), password),
        'SoundPathTW': ConvertString(obj.SoundPathTW(), password),
        'SoundPathEN': ConvertString(obj.SoundPathEN(), password),
        'SoundPathDE': ConvertString(obj.SoundPathDE(), password),
        'SoundPathFR': ConvertString(obj.SoundPathFR(), password),
    }

def dump_TutorialExcel(obj, password) -> dict:
    return {
        'ID': ConvertLong(obj.ID(), password),
        'CompletionReportEventName': ConvertString(obj.CompletionReportEventName(), password),
        'CompulsoryTutorial': obj.CompulsoryTutorial(),
        'DescriptionTutorial': obj.DescriptionTutorial(),
        'TutorialStageId': ConvertLong(obj.TutorialStageId(), password),
        'UIName': [ConvertString(obj.UIName(j), password) for j in range(obj.UINameLength())],
        'TutorialParentName': [ConvertString(obj.TutorialParentName(j), password) for j in range(obj.TutorialParentNameLength())],
    }

def dump_TutorialFailureImageExcel(obj, password) -> dict:
    return {
        'Id': ConvertLong(obj.Id(), password),
        'Contents': TutorialFailureContentType(ConvertInt(obj.Contents(), password)).name,
        'Type': ConvertString(obj.Type(), password),
        'ImagePathKr': ConvertString(obj.ImagePathKr(), password),
        'ImagePathJp': ConvertString(obj.ImagePathJp(), password),
        'ImagePathTh': ConvertString(obj.ImagePathTh(), password),
        'ImagePathTw': ConvertString(obj.ImagePathTw(), password),
        'ImagePathEn': ConvertString(obj.ImagePathEn(), password),
        'ImagePathDe': ConvertString(obj.ImagePathDe(), password),
        'ImagePathFr': ConvertString(obj.ImagePathFr(), password),
    }

def dump_VoiceCommonExcel(obj, password) -> dict:
    return {
        'VoiceEvent_': VoiceEvent(ConvertInt(obj.VoiceEvent_(), password)).name,
        'Rate': ConvertLong(obj.Rate(), password),
        'VoiceHash': [ConvertUInt(obj.VoiceHash(j), password) for j in range(obj.VoiceHashLength())],
    }

def dump_VoiceExcel(obj, password) -> dict:
    return {
        'NameHash': ConvertUInt(obj.NameHash(), password),
        'OnlyOne': obj.OnlyOne(),
        'VolumeJp': ConvertFloat(obj.VolumeJp(), password),
        'DelayJp': ConvertFloat(obj.DelayJp(), password),
        'Priority': ConvertInt(obj.Priority(), password),
        'AudioClipJp': ConvertString(obj.AudioClipJp(), password),
        'VolumeKr': ConvertFloat(obj.VolumeKr(), password),
        'DelayKr': ConvertFloat(obj.DelayKr(), password),
        'AudioClipKr': ConvertString(obj.AudioClipKr(), password),
        'VolumeTh': ConvertFloat(obj.VolumeTh(), password),
        'DelayTh': ConvertFloat(obj.DelayTh(), password),
        'AudioClipTh': ConvertString(obj.AudioClipTh(), password),
        'VolumeTw': ConvertFloat(obj.VolumeTw(), password),
        'DelayTw': ConvertFloat(obj.DelayTw(), password),
        'AudioClipTw': ConvertString(obj.AudioClipTw(), password),
        'VolumeEn': ConvertFloat(obj.VolumeEn(), password),
        'DelayEn': ConvertFloat(obj.DelayEn(), password),
        'AudioClipEn': ConvertString(obj.AudioClipEn(), password),
        'VolumeDe': ConvertFloat(obj.VolumeDe(), password),
        'DelayDe': ConvertFloat(obj.DelayDe(), password),
        'AudioClipDe': ConvertString(obj.AudioClipDe(), password),
        'VolumeFr': ConvertFloat(obj.VolumeFr(), password),
        'DelayFr': ConvertFloat(obj.DelayFr(), password),
        'AudioClipFr': ConvertString(obj.AudioClipFr(), password),
    }

def dump_VoiceLogicEffectExcel(obj, password) -> dict:
    return {
        'LogicEffectNameHash': ConvertUInt(obj.LogicEffectNameHash(), password),
        'Self': obj.Self(),
        'Priority': ConvertInt(obj.Priority(), password),
        'VoiceHash': [ConvertUInt(obj.VoiceHash(j), password) for j in range(obj.VoiceHashLength())],
        'VoiceId': ConvertUInt(obj.VoiceId(), password),
    }

def dump_VoiceSkillUseExcel(obj, password) -> dict:
    return {
        'Name': ConvertString(obj.Name(), password),
        'VoiceHash': [ConvertUInt(obj.VoiceHash(j), password) for j in range(obj.VoiceHashLength())],
    }

def dump_WeekDungeonExcel(obj, password) -> dict:
    return {
        'StageId': ConvertLong(obj.StageId(), password),
        'WeekDungeonType_': WeekDungeonType(ConvertInt(obj.WeekDungeonType_(), password)).name,
        'Difficulty': ConvertInt(obj.Difficulty(), password),
        'BattleDuration': ConvertLong(obj.BattleDuration(), password),
        'PrevStageId': ConvertLong(obj.PrevStageId(), password),
        'StageActionPointCostAmount': ConvertLong(obj.StageActionPointCostAmount(), password),
        'ConsumeTicket': obj.ConsumeTicket(),
        'GroundId': ConvertInt(obj.GroundId(), password),
        'StarGoal': [WeekDungeonStarGoalType(ConvertInt(obj.StarGoal(j), password)).name for j in range(obj.StarGoalLength())],
        'StarGoalAmount': [ConvertInt(obj.StarGoalAmount(j), password) for j in range(obj.StarGoalAmountLength())],
        'StageTopography_': StageTopography(ConvertInt(obj.StageTopography_(), password)).name,
        'RecommandLevel': ConvertLong(obj.RecommandLevel(), password),
        'StageRewardId': ConvertLong(obj.StageRewardId(), password),
        'PlayTimeLimitInSeconds': ConvertLong(obj.PlayTimeLimitInSeconds(), password),
        'BattleRewardExp': ConvertLong(obj.BattleRewardExp(), password),
        'BattleRewardPlayerExp': ConvertLong(obj.BattleRewardPlayerExp(), password),
        'GroupBuffID': [ConvertLong(obj.GroupBuffID(j), password) for j in range(obj.GroupBuffIDLength())],
    }

def dump_WeekDungeonFindGiftRewardExcel(obj, password) -> dict:
    return {
        'StageRewardId': ConvertLong(obj.StageRewardId(), password),
        'DevName': ConvertString(obj.DevName(), password),
        'RewardParcelType': [ParcelType(ConvertInt(obj.RewardParcelType(j), password)).name for j in range(obj.RewardParcelTypeLength())],
        'RewardParcelId': [ConvertLong(obj.RewardParcelId(j), password) for j in range(obj.RewardParcelIdLength())],
        'RewardParcelAmount': [ConvertLong(obj.RewardParcelAmount(j), password) for j in range(obj.RewardParcelAmountLength())],
        'RewardParcelProbability': [ConvertLong(obj.RewardParcelProbability(j), password) for j in range(obj.RewardParcelProbabilityLength())],
        'DropItemModelPrefabPath': [ConvertString(obj.DropItemModelPrefabPath(j), password) for j in range(obj.DropItemModelPrefabPathLength())],
    }

def dump_WeekDungeonGroupBuffExcel(obj, password) -> dict:
    return {
        'WeekDungeonBuffId': ConvertLong(obj.WeekDungeonBuffId(), password),
        'School_': School(ConvertInt(obj.School_(), password)).name,
        'RecommandLocalizeEtcId': ConvertUInt(obj.RecommandLocalizeEtcId(), password),
        'FormationLocalizeEtcId': ConvertUInt(obj.FormationLocalizeEtcId(), password),
        'SkillGroupId': ConvertString(obj.SkillGroupId(), password),
    }

def dump_WeekDungeonOpenScheduleExcel(obj, password) -> dict:
    return {
        'WeekDay_': WeekDay(ConvertInt(obj.WeekDay_(), password)).name,
        'Open': [WeekDungeonType(ConvertInt(obj.Open(j), password)).name for j in range(obj.OpenLength())],
    }

def dump_WeekDungeonRewardExcel(obj, password) -> dict:
    return {
        'GroupId': ConvertLong(obj.GroupId(), password),
        'DungeonType': WeekDungeonType(ConvertInt(obj.DungeonType(), password)).name,
        'RewardParcelType': ParcelType(ConvertInt(obj.RewardParcelType(), password)).name,
        'RewardParcelId': ConvertLong(obj.RewardParcelId(), password),
        'RewardParcelAmount': ConvertLong(obj.RewardParcelAmount(), password),
        'RewardParcelProbability': ConvertLong(obj.RewardParcelProbability(), password),
        'IsDisplayed': obj.IsDisplayed(),
        'DropItemModelPrefabPath': ConvertString(obj.DropItemModelPrefabPath(), password),
    }

from enum import IntEnum


class BubbleType(IntEnum):
    Idle = 0
    Monologue = 1
    EmoticonNormal = 2
    EmoticonFavorite = 3
    EmoticonReward = 4
    EmoticonGiveGift = 5

class FurnitureCategory(IntEnum):
    Furnitures = 0
    Decorations = 1
    Interiors = 2

class FurnitureSubCategory(IntEnum):
    Table = 0
    Closet = 1
    Chair = 2
    Bed = 3
    FurnitureEtc = 4
    FurnitureSubCategory1 = 5
    Prop = 6
    HomeAppliance = 7
    WallDecoration = 8
    FloorDecoration = 9
    DecorationEtc = 10
    DecorationSubCategory1 = 11
    Floor = 12
    Background = 13
    Wallpaper = 14
    InteriorsSubCategory1 = 15
    All = 16

class FurnitureLocation(IntEnum):
    none = 0
    Inventory = 1
    Floor = 2
    WallLeft = 3
    WallRight = 4

class AcademyMessageConditions(IntEnum):
    none = 0
    FavorRankUp = 1
    AcademySchedule = 2
    Answer = 3
    Feedback = 4

class AcademyMessageTypes(IntEnum):
    none = 0
    Text = 1
    Image = 2

class CafeCharacterState(IntEnum):
    none = 0
    Idle = 1
    Walk = 2
    Reaction = 3
    Speedrace = 4
    Hockey1 = 5
    Hockey2 = 6
    Max = 7

class VoiceEvent(IntEnum):
    OnTSA = 0
    FormationPickUp = 1
    CampaignResultDefeat = 2
    CampaignResultVictory = 3
    CharacterLevelUp = 4
    CharacterTranscendence = 5
    SkillLevelUp = 6
    Formation = 7
    CampaignCharacterSpawn = 8
    BattleStartTimeline = 9
    BattleVictoryTimeline = 10
    CharacterFavor = 11
    BattleMiss = 12
    BattleBlock = 13
    BattleCover = 14
    BattleMove = 15
    BattleMoveToForamtionBeacon = 16

class UnitType(IntEnum):
    none = 0
    AR = 1
    RF = 2
    HG = 3
    MG = 4
    SMG = 5
    SG = 6
    HZ = 7
    Melee = 8

class AttackType(IntEnum):
    Single = 0
    Splash = 1
    Through = 2
    Heal = 3

class ProjectileType(IntEnum):
    Guided = 0
    Ground = 1
    GuidedExplosion = 2
    GroundConstDistance = 3
    AirConstDistance = 4

class DamageFontColor(IntEnum):
    Blue = 0
    White = 1
    Yellow = 2
    Red = 3
    Green = 4

class TargetingCellType(IntEnum):
    none = 0
    Near = 1
    Far = 2

class TargetingUnitType(IntEnum):
    none = 0
    Near = 1
    Far = 2
    MinHp = 3
    MaxHp = 4
    Random = 5

class ProjectileAction(IntEnum):
    none = 0
    Damage = 1
    Heal = 2

class FontType(IntEnum):
    none = 0
    Damage = 1
    Block = 2
    Heal = 3
    Miss = 4
    Critical = 5
    Skill = 6
    Immune = 7
    DamageResist = 8
    DamageWeak = 9
    CriticalResist = 10
    CriticalWeak = 11

class EmoticonEvent(IntEnum):
    CoverEnter = 0
    ShelterEnter = 1
    Panic = 2
    NearlyDead = 3
    Reload = 4
    Found = 5
    GetBeacon = 6
    Warning = 7

class BulletType(IntEnum):
    Normal = 0
    Pierce = 1
    Explosion = 2
    Siege = 3
    Mystic = 4
    none = 5

class ActionType(IntEnum):
    Crush = 0
    Courage = 1
    Tactic = 2

class BuffOverlap(IntEnum):
    Able = 0
    Unable = 1
    Change = 2
    Additive = 3

class ReArrangeTargetType(IntEnum):
    AllySelf = 0
    AllyAll = 1
    AllyUnitType = 2
    AllyGroup = 3

class ArmorType(IntEnum):
    LightArmor = 0
    HeavyArmor = 1
    Unarmed = 2
    Structure = 3

class WeaponType(IntEnum):
    none = 0
    SG = 1
    SMG = 2
    AR = 3
    GL = 4
    HG = 5
    RL = 6
    SR = 7
    DSMG = 8
    RG = 9
    DSG = 10
    Vulcan = 11
    Missile = 12
    Cannon = 13
    Taser = 14
    MG = 15
    Binah = 16
    MT = 17
    Relic = 18

class EntityMaterialType(IntEnum):
    Wood = 0
    Stone = 1
    Flesh = 2
    Metal = 3

class CoverMotionType(IntEnum):
    All = 0
    Kneel = 1

class TargetSortBy(IntEnum):
    DISTANCE = 0
    HP = 1
    DAMAGE_EFFICIENCY = 2
    TARGETED_COUNT = 3
    RANDOM = 4
    FRONT_FORMATION = 5

class PositioningType(IntEnum):
    CloseToObstacle = 0
    CloseToTarget = 1

class DamageType(IntEnum):
    Normal = 0
    Critical = 1
    IgnoreDefence = 2

class FormationLine(IntEnum):
    Students = 0
    TSS = 1

class ExternalBTNodeType(IntEnum):
    Sequence = 0
    Selector = 1
    Instant = 2
    SubNode = 3
    ExecuteAll = 4

class ExternalBTTrigger(IntEnum):
    none = 0
    HPUnder = 1
    ApplySkillEffectCategory = 2
    HaveNextExSkillActiveGauge = 3
    UseNormalSkill = 4
    UseExSkill = 5
    CheckActiveGaugeOver = 6
    CheckPeriod = 7
    CheckSummonCharacterCountOver = 8
    CheckSummonCharacterCountUnder = 9
    ApplyGroggy = 10
    ApplyLogicEffectTemplateId = 11
    OnSpawned = 12
    CheckActiveGaugeBetween = 13
    DestroyParts = 14

class ExternalBehavior(IntEnum):
    UseNextExSkill = 0
    ChangePhase = 1
    ChangeSection = 2
    AddActiveGauge = 3
    UseSelectExSkill = 4
    ClearNormalSkill = 5
    MoveLeft = 6
    MoveRight = 7
    AllUseSelectExSkill = 8
    ConnectCharacterToDummy = 9
    ConnectExSkillToParts = 10
    SetMaxHPToParts = 11
    AlivePartsUseExSkill = 12
    ActivatePart = 13
    AddGroggy = 14

class TacticEntityType(IntEnum):
    none = 0
    Student = 1
    Minion = 2
    Elite = 4
    Champion = 8
    Boss = 16
    Obstacle = 32
    Servant = 64
    Vehicle = 128
    Summoned = 256

class BuffIconType(IntEnum):
    none = 0
    Debuff_DyingPenalty = 1
    CC_MindControl = 2
    CC_Inoperative = 3
    CC_Confusion = 4
    CC_Provoke = 5
    CC_Silence = 6
    CC_Blind = 7
    Dot_Damage = 8
    Dot_Heal = 9
    Buff_AttackPower = 10
    Buff_CriticalChance = 11
    Buff_CriticalDamage = 12
    Buff_DefensePower = 13
    Buff_Dodge = 14
    Buff_Hit = 15
    Buff_WeaponRange = 16
    Buff_SightRange = 17
    Buff_MoveSpeed = 18
    Buff_Mind = 19
    Debuf_AttackPower = 20
    Debuff_CriticalChance = 21
    Debuff_CriticalDamage = 22
    Debuff_DefensePower = 23
    Debuff_Dodge = 24
    Debuff_Hit = 25
    Debuff_WeaponRange = 26
    Debuff_SightRange = 27
    Debuff_MoveSpeed = 28
    Debuff_Mind = 29
    Buff_AttackTime = 30
    Debuff_AttackTime = 31
    Buff_MaxHp = 32
    Debuff_MaxHp = 33
    Buff_MaxBulletCount = 34
    Debuff_MaxBulletCount = 35
    Debuff_SuppliesCondition = 36
    Buff_HealEffectivenessRate = 37
    Debuff_HealEffectivenessRate = 38
    Buff_HealPower = 39
    Debuff_HealPower = 40
    Buff_CriticalChanceResistPoint = 41
    Debuff_CriticalChanceResistPoint = 42
    CC_Stunned = 43
    Debuff_ConcentratedTarget = 44
    Buff_Immortal = 45
    Max = 46

class Difficulty(IntEnum):
    Normal = 0
    Hard = 1
    VeryHard = 2
    Hardcore = 3
    Extreme = 4
    Insane = 5

class EngageType(IntEnum):
    SearchAndMove = 0
    HoldPosition = 1

class HitEffectPosition(IntEnum):
    Position = 0
    HeadBone = 1
    BodyBone = 2
    Follow = 3

class StageTopography(IntEnum):
    Street = 0
    Outdoor = 1
    Indoor = 2

class TerrainAdaptationStat(IntEnum):
    D = 0
    C = 1
    B = 2
    A = 3
    S = 4
    SS = 5

class SquadType(IntEnum):
    none = 0
    Main = 1
    Support = 2
    TSS = 3

class ObstacleClass(IntEnum):
    MAIN = 0
    SUB = 1

class ObstacleDestroyType(IntEnum):
    Remain = 0
    Remove = 1

class ObstacleHeightType(IntEnum):
    Low = 0
    Middle = 1
    High = 2

class ObstacleCoverType(IntEnum):
    none = 0
    Cover = 1
    Shelter = 2

class SkillCategory(IntEnum):
    none = 0

class LogicEffectCategory(IntEnum):
    none = 0
    Attack = 1
    Heal = 2
    Buff = 3
    Debuff = 4
    CrowdControl = 5
    Boss = 6
    Dummy = 7

class AimIKType(IntEnum):
    none = 0
    OneHandRight = 1
    OneHandLeft = 2
    TwoHandRight = 3
    TwoHandLeft = 4
    Tripod = 5
    Dual = 6
    Max = 7

class DamageAttribute(IntEnum):
    Resist = 0
    Normal = 1
    Weak = 2

class SkillPriorityCheckCondition(IntEnum):
    none = 0
    HPRateUnder = 1
    DebuffCountOver = 2
    BuffCountOver = 3
    CrowdControlOver = 4

class SkillPriorityCheckTarget(IntEnum):
    Ally = 0
    Enemy = 1
    All = 2

class StageType(IntEnum):
    Main = 0
    Sub = 1

class OperatorCondition(IntEnum):
    none = 0
    StrategyStart = 1
    StrategyVictory = 2
    StrategyDefeat = 3
    AdventureCombatStart = 4
    AdventureCombatVictory = 5
    AdventureCombatDefeat = 6
    ArenaCombatStart = 7
    ArenaCombatVictory = 8
    ArenaCombatDefeat = 9
    WeekDungeonCombatStart = 10
    WeekDungeonCombatVictory = 11
    WeekDungeonCombatDefeat = 12
    SchoolDungeonCombatStart = 13
    SchoolDungeonCombatVictory = 14
    SchoolDungeonCombatDefeat = 15
    StrategyWarpUnitFromHideTile = 16

class KnockbackDirection(IntEnum):
    TargetToCaster = 0
    CasterToTarget = 1
    TargetToHitPosition = 2
    HitPositionToTarget = 3
    CasterToHitPosition = 4
    HitPositionToCaster = 5

class EndCondition(IntEnum):
    Duration = 0
    ReloadCount = 1
    AmmoCount = 2
    AmmoHit = 3
    HitCount = 4
    none = 5
    UseExSkillCount = 6

class LogicEffectSound(IntEnum):
    none = 0
    Damage = 1
    Heal = 2
    Knockback = 3

class EffectBone(IntEnum):
    none = 0
    Shot = 1
    Head = 2
    Body = 3
    Shot2 = 4
    Shot3 = 5
    Extra = 6
    Extra2 = 7
    Extra3 = 8

class ArenaSimulatorServer(IntEnum):
    Preset = 0
    Live = 1
    Dev = 2
    QA = 3

class ClearCheck(IntEnum):
    none = 0
    Success_Play = 1
    Success_Sweep = 2
    Fail_Timeout = 3
    Fail_PlayerGiveUp = 4
    Fail_Annihilation = 5

class BuffType(IntEnum):
    none = 0
    Buff_AttackPower = 1
    Buff_CriticalChance = 2
    Buff_CriticalDamage = 3
    Buff_DefensePower = 4
    Buff_Dodge = 5
    Buff_Hit = 6
    Buff_WeaponRange = 7
    Buff_SightRange = 8
    Buff_MoveSpeed = 9
    Buff_AttackTime = 10
    Buff_MaxHp = 11
    Buff_MaxBulletCount = 12
    DeBuff_AttackPower = 13
    DeBuff_CriticalChance = 14
    DeBuff_CriticalDamage = 15
    DeBuff_DefensePower = 16
    DeBuff_Dodge = 17
    DeBuff_Hit = 18
    DeBuff_WeaponRange = 19
    DeBuff_SightRange = 20
    DeBuff_MoveSpeed = 21
    DeBuff_AttackTime = 22
    DeBuff_MaxHp = 23
    DeBuff_MaxBulletCount = 24

class NexonBillingState(IntEnum):
    ValiDateWait = 0
    ValiDateFail = 1
    ValiDateSuccess = 2
    Finish = 3

class StatLevelUpType(IntEnum):
    Standard = 0
    Premature = 1
    LateBloom = 2

class GrowthCategory(IntEnum):
    none = 0
    LevelUp = 1
    Transcend = 2
    SkillLevelUp = 3

class StatType(IntEnum):
    none = 0
    MaxHP = 1
    AttackPower = 2
    DefensePower = 3
    HealPower = 4
    AccuracyPoint = 5
    AccuracyRate = 6
    DodgePoint = 7
    DodgeRate = 8
    CriticalPoint = 9
    CriticalChanceRate = 10
    CriticalResistChanceRate = 11
    CriticalDamageRate = 12
    MoveSpeed = 13
    SightRange = 14
    ActiveGauge = 15
    StabilityPoint = 16
    StabilityRate = 17
    ReloadTime = 18
    MaxBulletCount = 19
    IgnoreDelayCount = 20
    WeaponRange = 21
    BlockRate = 22
    BodyRadius = 23
    ActionCount = 24
    StrategyMobility = 25
    StrategySightRange = 26
    StreetBattleAdaptation = 27
    OutdoorBattleAdaptation = 28
    IndoorBattleAdaptation = 29
    HealEffectivenessRate = 30
    CriticalChanceResistPoint = 31
    CriticalDamageResistRate = 32
    LifeRecoverOnHit = 33
    NormalAttackSpeed = 34
    AmmoCost = 35
    GroggyGauge = 36
    GroggyTime = 37
    DamageRatio = 38
    DamagedRatio = 39
    OppressionPower = 40
    OppressionResist = 41
    RegenCost = 42
    InitialWeaponRangeRate = 43
    DefensePenetration = 44
    Max = 45

class ProductionStep(IntEnum):
    ToDo = 0
    Doing = 1
    Complete = 2
    Release = 3

class TacticRole(IntEnum):
    DamageDealer = 0
    Tanker = 1
    Supporter = 2
    Healer = 3
    Vehicle = 4

class TacticRange(IntEnum):
    Back = 0
    Front = 1
    Middle = 2

class ClanSocialGrade(IntEnum):
    none = 0
    President = 1
    Manager = 2
    Member = 3
    Applicant = 4
    Refused = 5
    Kicked = 6
    Quit = 7
    VicePredisident = 8

class ClanJoinOption(IntEnum):
    Free = 0
    Permission = 1
    All = 2

class ClanSearchOption(IntEnum):
    Name = 0
    Id = 1

class ClanRewardType(IntEnum):
    none = 0
    AssistTerm = 1
    AssistRent = 2
    Attendance = 3

class ContentType(IntEnum):
    none = 0
    CampaignMainStage = 1
    CampaignSubStage = 2
    WeekDungeon = 3
    EventContentMainStage = 4
    EventContentSubStage = 5
    CampaignTutorialStage = 6
    EventContentMainGroundStage = 7
    SchoolDungeon = 8

class EventContentType(IntEnum):
    Stage = 0
    Gacha = 1
    Mission = 2
    Shop = 3
    Raid = 4
    Arena = 5
    BoxGacha = 6
    Collection = 7
    Recollection = 8
    MiniGameRhythm = 9
    CardShop = 10

class OpenCondition(IntEnum):
    Hide = 0
    Lock = 1
    Open = 2

class ResetContentType(IntEnum):
    none = 0
    HardStagePlay = 1
    StarategyMapHeal = 2
    ShopRefresh = 3
    ArenaDefenseVictoryReward = 4

class WeekDungeonType(IntEnum):
    none = 0
    ChaserA = 1
    ChaserB = 2
    ChaserC = 3
    FindGift = 4
    Blood = 5

class WeekDungeonStarGoalType(IntEnum):
    none = 0
    AllAlive = 1
    Clear = 2
    GetBoxes = 3
    ClearTimeInSec = 4

class OpenConditionContent(IntEnum):
    Shop = 0
    Gacha = 1
    LobbyIllust = 2
    Raid = 3
    Cafe = 4
    Unit_Growth_Skill = 5
    Unit_Growth_LevelUp = 6
    Unit_Growth_Transcendence = 7
    Arena = 8
    Academy = 9
    Equip = 10
    Item = 11
    Favor = 12
    Prologue = 13
    Mission = 14
    WeekDungeon_Chase = 15
    __Deprecated_WeekDungeon_FindGift = 16
    __Deprecated_WeekDungeon_Blood = 17
    Story_Sub = 18
    Story_Replay = 19
    WeekDungeon = 20
    none = 21
    Shop_Gem = 22
    Craft = 23
    Student = 24
    GuideMission = 25
    Clan = 26
    Echelon = 27
    Campaign = 28
    EventContent = 29
    Guild = 30
    EventStage_1 = 31
    EventStage_2 = 32
    Talk = 33
    Billing = 34
    Schedule = 35
    Story = 36
    Tactic_Speed = 37
    Cafe_Invite = 38
    EventMiniGame_1 = 39
    SchoolDungeon = 40

class ContentLockType(IntEnum):
    none = 0
    NotUseControlledByOtherSetting = 1
    Academy = 2
    Arena = 3
    Billing = 4
    Cafe = 5
    Campaign = 6
    Clan = 7
    Craft = 8
    Echelon = 9
    Equipment = 10
    EventContent = 11
    EventStage_1 = 12
    EventStage_2 = 13
    Favor = 14
    Gacha = 15
    GuideMission = 16
    Item = 17
    LobbyIllust = 18
    Mission = 19
    MomoTalk = 20
    Raid = 21
    Schedule = 22
    Shop = 23
    SkipHistorySave = 24
    Story = 25
    Unit_Growth_LevelUp = 26
    Unit_Growth_Skill = 27
    Unit_Growth_Transcendence = 28
    WeekDungeon = 29
    WeekDungeon_Chase = 30
    SchoolDungeon = 31

class TutorialFailureContentType(IntEnum):
    none = 0
    Campaign = 1
    WeekDungeon = 2
    Raid = 3

class FeverBattleType(IntEnum):
    Campaign = 0
    Raid = 1
    WeekDungeon = 2
    Arena = 3

class EventContentScenarioConditionType(IntEnum):
    none = 0
    DayAfter = 1
    EventPoint = 2

class EventTargetType(IntEnum):
    WeekDungeon = 0
    Chaser = 1
    Campaign_Normal = 2
    Campaign_Hard = 3
    SchoolDungeon = 4

class ContentResultType(IntEnum):
    Failure = 0
    Success = 1

class EventContentItemType(IntEnum):
    EventPoint = 0
    EventToken1 = 1
    EventToken2 = 2
    EventToken3 = 3
    EventToken4 = 4
    EventToken5 = 5

class RaidSeasonType(IntEnum):
    none = 0
    Open = 1
    Close = 2
    Settlement = 3

class BuffConditionType(IntEnum):
    All = 0
    Character = 1
    School = 2
    Weapon = 3

class EventCollectionUnlockType(IntEnum):
    none = 0
    ClearSpecificEventStage = 1
    ClearSpecificEventScenario = 2
    ClearSpecificEventMission = 3
    PurchaseSpecificItemCount = 4

class ShortcutContentType(IntEnum):
    none = 0
    CampaignStage = 1
    EventStage = 2
    Blood = 3
    WeekDungeon = 4
    Arena = 5
    Raid = 6
    Shop = 7

class JudgeGrade(IntEnum):
    none = 0
    Miss = 1
    Attack = 2
    Critical = 3

class SchoolDungeonType(IntEnum):
    SchoolA = 0
    SchoolB = 1
    SchoolC = 2

class EquipmentCategory(IntEnum):
    Unable = 0
    Exp = 1
    Bag = 2
    Hat = 3
    Gloves = 4
    Shoes = 5
    Badge = 6
    Hairpin = 7
    Charm = 8
    Watch = 9
    Necklace = 10
    WeaponExpGrowthA = 11
    WeaponExpGrowthB = 12
    WeaponExpGrowthC = 13
    WeaponExpGrowthZ = 14

class EquipmentOptionType(IntEnum):
    none = 0
    MaxHP_Base = 1
    MaxHP_Coefficient = 2
    AttackPower_Base = 3
    AttackPower_Coefficient = 4
    DefensePower_Base = 5
    DefensePower_Coefficient = 6
    HealPower_Base = 7
    HealPower_Coefficient = 8
    CriticalPoint_Base = 9
    CriticalPoint_Coefficient = 10
    CriticalChanceRate_Base = 11
    CriticalDamageRate_Base = 12
    CriticalDamageRate_Coefficient = 13
    SightRange_Base = 14
    SightRange_Coefficient = 15
    MaxBulletCount_Base = 16
    MaxBulletCount_Coefficient = 17
    HPRecoverOnKill_Base = 18
    HPRecoverOnKill_Coefficient = 19
    StreetBattleAdaptation_Base = 20
    OutdoorBattleAdaptation_Base = 21
    IndoorBattleAdaptation_Base = 22
    HealEffectivenessRate_Base = 23
    HealEffectivenessRate_Coefficient = 24
    CriticalChanceResistPoint_Base = 25
    CriticalChanceResistPoint_Coefficient = 26
    CriticalDamageResistRate_Base = 27
    CriticalDamageResistRate_Coefficient = 28
    ExSkillUpgrade = 29
    OppressionPower_Base = 30
    OppressionPower_Coefficient = 31
    OppressionResist_Base = 32
    OppressionResist_Coefficient = 33
    StabilityPoint_Base = 34
    StabilityPoint_Coefficient = 35
    AccuracyPoint_Base = 36
    AccuracyPoint_Coefficient = 37
    DodgePoint_Base = 38
    DodgePoint_Coefficient = 39
    MoveSpeed_Base = 40
    MoveSpeed_Coefficient = 41
    Max = 42

class MultipleConditionCheckType(IntEnum):
    And = 0
    Or = 1

class Language(IntEnum):
    Kr = 0
    Jp = 1
    Th = 2
    Tw = 3
    En = 4
    De = 5
    Fr = 6

class SoundType(IntEnum):
    UI = 0
    BGM = 1
    FX = 2

class WeekDay(IntEnum):
    Sunday = 0
    Monday = 1
    Tuesday = 2
    Wednesday = 3
    Thursday = 4
    Friday = 5
    Saturday = 6
    All = 7

class EchelonType(IntEnum):
    none = 0
    Adventure = 1
    Raid = 2
    ArenaAttack = 3
    ArenaDefence = 4
    WeekDungeonChaserA = 5
    Scenario = 6
    WeekDungeonBlood = 7
    WeekDungeonChaserB = 8
    WeekDungeonChaserC = 9
    WeekDungeonFindGift = 10
    EventContent = 11
    SchoolDungeonA = 12
    SchoolDungeonB = 13
    SchoolDungeonC = 14

class NoticeType(IntEnum):
    none = 0
    Notice = 1
    Event = 2

class RewardTag(IntEnum):
    Default = 0
    FirstClear = 1
    StrategyObject = 2
    Event = 3
    ThreeStar = 4
    ProductMonthly = 5
    Rare = 6
    EventBonus = 7

class ArenaRewardType(IntEnum):
    none = 0
    Time = 1
    Daily = 2
    SeasonRecord = 3
    OverallRecord = 4
    SeasonClose = 5
    AttackVictory = 6
    DefenseVictory = 7
    RankIcon = 8

class ServiceActionType(IntEnum):
    ClanCreate = 0
    HardAdventurePlayCountRecover = 1

class RaidStatus(IntEnum):
    none = 0
    Playing = 1
    Clear = 2
    Close = 3

class WebAPIErrorLevel(IntEnum):
    none = 0
    Warning = 1
    Error = 2

class AccountBanType(IntEnum):
    none = 0
    AbuseGamePlay = 1
    AbuseMarket = 2
    AbuseGameSystem = 3
    OperaionPolicyViolate = 4
    Useillegalprogram = 5
    Temporaryconstraint = 6

class ItemCategory(IntEnum):
    Coin = 0
    CharacterExpGrowth = 1
    SecretStone = 2
    Material = 3
    Consumable = 4
    Collectible = 5
    Favor = 6
    RecruitCoin = 7
    MonthlyBonus = 8

class MailType(IntEnum):
    System = 0
    Attendance = 1
    Event = 2
    MassTrade = 3
    InventoryFull = 4
    ArenaDefenseVictory = 5
    CouponUsageReward = 6
    ArenaSeasonClose = 7
    ProductReward = 8
    MonthlyProductReward = 9
    ExpiryChangeItem = 10
    ClanAttendance = 11
    AccountLink = 12
    NewUserBonus = 13
    LeftClanAssistReward = 14
    CashShopBuy = 15
    MonthlyProductPackage = 16

class AttendanceType(IntEnum):
    Basic = 0
    Event = 1
    Newbie = 2

class AttendanceCountRule(IntEnum):
    Accumulation = 0
    Date = 1

class AttendanceResetType(IntEnum):
    User = 0
    Server = 1

class MissionCategory(IntEnum):
    Challenge = 0
    Daily = 1
    Weekly = 2
    Achievement = 3
    GuideMission = 4
    All = 5
    MiniGameScore = 6
    MiniGameEvent = 7
    EventAchievement = 8

class MissionResetType(IntEnum):
    none = 0
    Daily = 1
    Weekly = 2

class MissionCompleteConditionType(IntEnum):
    none = 0
    DailyLogin = 1
    DailyLoginCount = 2
    CompleteMission = 3
    EquipmentLevelUpCount = 4
    EquipmentTierUpCount = 5
    CharacterLevelUpCount = 6
    CharacterTranscendenceCount = 7
    ClearTaticBattleCount = 8
    ClearCampaignStageCount = 9
    KillSpecificEnemyCount = 10
    KillEnemyWithTagCount = 11
    GetCharacterCount = 12
    GetCharacterWithTagCount = 13
    GetSpecificCharacterCount = 14
    AccountLevelUp = 15
    GetEquipmentCount = 16
    GachaCount = 17
    UseGem = 18
    GetGem = 19
    GetGemPaid = 20
    GetGold = 21
    GetItem = 22
    GetFavorLevel = 23
    EquipmentAtSpecificLevelCount = 24
    EquipmentAtSpecificTierUpCount = 25
    CharacterAtSpecificLevelCount = 26
    CharacterAtSpecificTranscendenceCount = 27
    CharacterSkillLevelUpCount = 28
    CharacterAtSpecificSkillLevelCount = 29
    CompleteScheduleCount = 30
    CompleteScheduleGroupCount = 31
    AcademyLocationRankSum = 32
    CraftCount = 33
    GetComfortPoint = 34
    GetWeaponCount = 35
    EquipWeaponCount = 36
    CompleteScheduleWithSpecificCharacter = 37
    CafeInteractionCount = 38
    SpecificCharacterAtSpecificLevel = 39
    SpecificCharacterAtSpecificTranscendence = 40
    LobbyInteraction = 41
    ClearWeekDungeonCount = 42
    ClearSpecificWeekDungeonCount = 43
    JoinRaidCount = 44
    JoinSpecificRaidCount = 45
    JoinArenaCount = 46
    ArenaVictoryCount = 47
    RaidDamageAmountOnOneBattle = 48
    ClearEventStageCount = 49
    UseSpecificCharacterCount = 50
    UseGold = 51
    UseTiket = 52
    ShopBuyCount = 53
    ShopBuyActionPointCount = 54
    SpecificCharacterAtSpecificFavorRank = 55
    ClearSpecificScenario = 56
    GetSpecificItemCount = 57
    TotalGetClearStarCount = 58
    CompleteCampaignStageMinimumTurn = 59
    TotalLoginCount = 60
    LoginAtSpecificTime = 61
    CompleteFavorSchedule = 62
    CompleteFavorScheduleAtSpecificCharacter = 63
    GetMemoryLobbyCount = 64
    GetFurnitureGroupCount = 65
    AcademyLocationAtSpecificRank = 66
    ClearCampaignStageDifficultyNormal = 67
    ClearCampaignStageDifficultyHard = 68
    ClearChaserDungeonCount = 69
    ClearSpecificChaserDungeonCount = 70
    GetCafeRank = 71
    SpecificStarCharacterCount = 72
    EventClearCampaignStageCount = 73
    EventClearSpecificCampaignStageCount = 74
    EventCompleteCampaignStageMinimumTurn = 75
    EventClearCampaignStageDifficultyNormal = 76
    EventClearCampaignStageDifficultyHard = 77
    ClearSpecificCampaignStageCount = 78
    GetItemWithTagCount = 79
    GetFurnitureWithTagCount = 80
    GetEquipmentWithTagCount = 81
    ClearCampaignStageTimeLimitFromSecond = 82
    ClearEventStageTimeLimitFromSecond = 83
    ClearRaidTimeLimitFromSecond = 84
    ClearBattleWithTagCount = 85
    ClearWeekDungeonTimeLimitFromSecond = 86
    CompleteScheduleWithTagCount = 87
    ClearChaserDungeonTimeLimitFromSecond = 88
    GetTotalScoreRhythm = 89
    GetBestScoreRhythm = 90
    GetSpecificScoreRhythm = 91
    ClearStageRhythm = 92
    GetComboCountRhythm = 93
    GetFullComboRhythm = 94
    GetFeverCountRhythm = 95
    UseActionPoint = 96

class AccountAchievementType(IntEnum):
    TotalLoginCount = 0
    TotalGetClearStarCount = 1
    TotalCharacterLevelUpCount = 2
    TotalCharacterSkillLevelUpCount = 3
    TotalClearCampaignStageCount = 4
    TotalClearChaserDungeonCount = 5
    TotalClearWeekDungeonCount = 6
    TotalEquipmentLevelUpCount = 7
    TotalEquipmentTierUpCount = 8
    MaxComfortPoint = 9
    TotalGetGold = 10
    TotalUseGold = 11
    TotalJoinArenaCount = 12
    TotalJoinRaidCount = 13

class ParcelType(IntEnum):
    none = 0
    Character = 1
    Currency = 2
    Equipment = 3
    Item = 4
    GachaGroup = 5
    Product = 6
    Shop = 7
    MemoryLobby = 8
    AccountExp = 9
    CharacterExp = 10
    FavorExp = 11
    TSS = 12
    Furniture = 13
    ShopRefresh = 14
    LocationExp = 15
    Recipe = 16
    CharacterWeapon = 17
    ProductMonthly = 18

class Rarity(IntEnum):
    N = 0
    R = 1
    SR = 2
    SSR = 3

class Tier(IntEnum):
    T1 = 0
    T2 = 1
    T3 = 2
    T4 = 3

class CurrencyTypes(IntEnum):
    Invalid = 0
    Gold = 1
    GemPaid = 2
    GemBonus = 3
    Gem = 4
    ActionPoint = 5
    AcademyTicket = 6
    ArenaTicket = 7
    RaidTicket = 8
    WeekDungeonChaserATicket = 9
    WeekDungeonFindGiftTicket = 10
    WeekDungeonBloodTicket = 11
    WeekDungeonChaserBTicket = 12
    WeekDungeonChaserCTicket = 13
    SchoolDungeonATicket = 14
    SchoolDungeonBTicket = 15
    SchoolDungeonCTicket = 16
    MasterCoin = 17
    Max = 18

class SortingTarget(IntEnum):
    none = 0
    Rarity = 1
    Level = 2
    StarGrade = 3
    Tier = 4

class CurrencyOverChargeType(IntEnum):
    CanNotCharge = 0
    FitToLimit = 1
    ChargeOverLimit = 2

class CurrencyAdditionalChargeType(IntEnum):
    EnableAutoChargeOverLimit = 0
    DisableAutoChargeOverLimit = 1

class RecipeType(IntEnum):
    none = 0
    Craft = 1
    SkillLevelUp = 2
    CharacterTranscendence = 3
    EquipmentTierUp = 4
    CafeRankUp = 5
    SelectionItem = 6

class GachaGroupType(IntEnum):
    none = 0
    Reward_General = 1
    System_Craft = 2

class ParcelChangeReason(IntEnum):
    none = 0
    Acquire_NewAccount = 1
    Acquire_PlayReward = 2
    Acquire_ChapterReward = 3
    Acquire_LoginReward = 4
    Acquire_EventReward = 5
    Acquire_GMPush = 6
    Acquire_ShopBuy = 7
    Acquire_GachaBuy = 8
    Acquire_CurrencyBuy = 9
    Equipment_Equip = 10
    Equipment_Unequip = 11
    Equipment_Levelup = 12
    Equipment_LimitBreak = 13
    Equipment_Transcendence = 14
    Equipment_Enchant = 15
    Item_Use = 16
    Item_Lock = 17
    Item_CharacterGrowthMaterial = 18
    Item_Change = 19
    Item_Delete = 20
    Item_Consume = 21
    Item_SelectTicket = 22
    Character_ExpGrowth = 23
    Character_Transcendence = 24
    Character_SkillLevelUp = 25
    Character_FavorGrowth = 26
    Furniture_CafeSet = 27
    Furniture_CafeRecall = 28
    Academy_AttendSchedule = 29
    Academy_MessageList = 30
    Adventure_EnterMainStage = 31
    Adventure_EnterSubStage = 32
    Adventure_MainStageBattleResult = 33
    Adventure_SubStageBattleResult = 34
    Adventure_ChapterClearReward = 35
    Adventure_Retreat = 36
    Adventure_PurchasePlayCountHardStage = 37
    Adventure_TutorialStage = 38
    Adventure_TutorialStageBattleResult = 39
    ContentSweep_Sweep = 40
    Arena_TimeReward = 41
    Arena_DailyReward = 42
    Arena_EnterBattle = 43
    Arena_BattleResult = 44
    Cafe_Interact = 45
    Cafe_Production = 46
    Cafe_RankUp = 47
    Cafe_GiveGift = 48
    WeekDungeon_BattleResult = 49
    WeekDungeon_EnterBattle = 50
    WeekDungeon_Retreat = 51
    Mission_Clear = 52
    Shop_Refresh = 53
    Shop_BuyEligma = 54
    Shop_BuyMerchandise = 55
    Shop_BuyGacha = 56
    Scenario_Clear = 57
    Recipe_Craft = 58
    Raid_Failed = 59
    Raid_Reward = 60
    Raid_SeasonReward = 61
    Raid_CreateBattle = 62
    CumulativeTimeReward_Reward = 63
    Mail_Receive = 64
    MomoTalk_FavorSchedule = 65
    WeekDungeon_EnterBlood = 66
    WeekDungeon_EnterGift = 67
    Acquire_ActionPoint = 68
    Acquire_ArenaTicket = 69
    EventContent_TotalReward = 70
    Craft_UpdateNode = 71
    Craft_CompleteProcess = 72
    Craft_Reward = 73
    EventContent_BattleResult = 74
    Adventure_Sweep = 75
    EventContent_Sweep = 76
    WeekDungeon_Sweep = 77
    Acquire_MonthlyProduct = 78
    Acquire_DailyReward = 79
    Billing_PurchaseProduct = 80
    EventContent_EnterMainStage = 81
    EventContent_EnterSubStage = 82
    EventContent_MainStageResult = 83
    EventContent_SubStageResult = 84
    EventContent_Retreat = 85
    WeekDungeon_BloodResult = 86
    WeekDungeon_GiftResult = 87
    WeekDungeon_EnterChaserA = 88
    WeekDungeon_EnterChaserB = 89
    WeekDungeon_EnterChaserC = 90
    WeekDungeon_ChaserAResult = 91
    WeekDungeon_ChaserBResult = 92
    WeekDungeon_ChaserCResult = 93
    EventContent_BoxGacha = 94
    Raid_Sweep = 95
    Clan_AssistReward = 96
    EventContent_CardShop = 97
    CharacterWeapon_ExpGrowth = 98
    CharacterWeapon_Transcendence = 99
    MiniGameMission_Clear = 100
    Clan_Create = 101
    ContentDiscard_Currency = 102

class ScenarioBGType(IntEnum):
    none = 0
    Image = 1
    BlurRT = 2
    Spine = 3
    Hide = 4

class ScenarioType(IntEnum):
    none = 0
    Title = 1
    Place = 2

class ScenarioTypes(IntEnum):
    none = 0
    Title = 1
    Place = 2

class ScenarioCharacterAction(IntEnum):
    Idle = 0
    Shake = 1
    Greeting = 2
    FalldownLeft = 3
    FalldownRight = 4
    Stiff = 5
    Hophop = 6
    Jump = 7

class ScenarioCharacterBehaviors(IntEnum):
    none = 0
    Appear = 1
    Disappear = 2
    AppearToLeft = 3
    ApperToRight = 4
    DisappearToLeft = 5
    DisappearToRight = 6
    MoveToTarget = 7

class ScenarioCharacterShapes(IntEnum):
    none = 0
    Signal = 1
    BlackSilhouette = 2
    Closeup = 4
    Highlight = 8

class ScenarioBGScroll(IntEnum):
    none = 0
    Vertical = 1
    Horizontal = 2

class DialogCategory(IntEnum):
    Cafe = 0
    Echelon = 1
    CharacterSSRNew = 2
    CharacterGet = 3
    Birthday = 4
    Dating = 5
    Title = 6
    UILobby = 7
    UILobbySpecial = 8
    UIShop = 9
    UIGacha = 10
    UIRaidLobby = 11
    UIWork = 12
    UITitle = 13
    UIWeekDungeon = 14
    UIAcademyLobby = 15
    UIRaidLobbySeasonOff = 16
    UIRaidLobbySeasonOn = 17
    UIWorkAronaSit = 18
    UIWorkAronaSleep = 19
    UIWorkAronaWatch = 20
    UIGuideMission = 21
    UILobby2 = 22
    UIClanSearchList = 23
    UIAttendance = 24
    UIAttendanceEvent01 = 25
    UIEventLobby = 26
    UIEventShop = 27
    UIEventBoxGachaShop = 28
    UIAttendanceEvent02 = 29
    UIAttendanceEvent03 = 30
    UIEventCardShop = 31
    UISchoolDungeon = 32

class DialogCondition(IntEnum):
    Idle = 0
    Enter = 1
    Exit = 2
    Buy = 3
    SoldOut = 4
    BoxGachaNormal = 5
    BoxGachaPrize = 6
    Prize0 = 7
    Prize1 = 8
    Prize2 = 9
    Prize3 = 10

class DialogConditionDetail(IntEnum):
    none = 0
    Day = 1
    Close = 2

class DialogType(IntEnum):
    Talk = 0
    Think = 1
    UITalk = 2

class Anniversary(IntEnum):
    none = 0
    UserBDay = 1
    StudentBDay = 2

class School(IntEnum):
    none = 0
    Hyakkiyako = 1
    RedWinter = 2
    Trinity = 3
    Gehenna = 4
    Abydos = 5
    Millennium = 6
    Arius = 7
    Shanhaijing = 8
    Valkyrie = 9
    WildHunt = 10
    SRT = 11

class StoryCondition(IntEnum):
    Open = 0
    Locked = 1
    ComingSoon = 2
    Hide = 3

class EmojiEvent(IntEnum):
    EnterConver = 0
    EnterShelter = 1
    SignalLeader = 2
    Nice = 3
    Reload = 4
    Blind = 5
    Panic = 6
    Silence = 7
    NearyDead = 8
    Run = 9
    TerrainAdaptionS = 10
    TerrainAdaptionA = 11
    TerrainAdaptionB = 12
    TerrainAdaptionC = 13
    TerrainAdaptionD = 14
    TerrainAdaptionSS = 15

class ScenarioModeTypes(IntEnum):
    none = 0
    Main = 1
    Sub = 2
    Replay = 3

class ScenarioModeSubTypes(IntEnum):
    none = 0
    Club = 1
    TSS = 2

class ScenarioModeReplayTypes(IntEnum):
    none = 0
    Event = 1
    Favor = 2
    Work = 3

class ScenarioEffectDepth(IntEnum):
    none = 0
    AboveBg = 1
    AboveCharacter = 2
    AboveAll = 3

class ScenarioZoomAnchors(IntEnum):
    Center = 0
    LeftTop = 1
    LeftBottom = 2
    RightTop = 3
    RightBottom = 4

class ScenarioZoomType(IntEnum):
    Instant = 0
    Slide = 1

class ScenarioContentType(IntEnum):
    Prologue = 0
    WeekDungeon = 1
    Raid = 2
    Arena = 3
    Favor = 4
    Shop = 5
    EventContent = 6
    Craft = 7
    Chaser = 8

class PurchaseCountResetType(IntEnum):
    none = 0
    Day = 1
    Week = 2
    Month = 3

class ShopCategoryType(IntEnum):
    General = 0
    SecretStone = 1
    Raid = 2
    Gold = 3
    Ap = 4
    PickupGacha = 5
    NormalGacha = 6
    PointGacha = 7
    EventGacha = 8
    ArenaTicket = 9
    Arena = 10
    TutoGacha = 11
    RecruitSellection = 12
    EventContent_0 = 13
    EventContent_1 = 14
    EventContent_2 = 15
    EventContent_3 = 16
    EventContent_4 = 17
    ThreeStarGacha = 18
    LimitedGacha = 19
    MasterCoin = 20

class PurchaseServerTag(IntEnum):
    Audit = 0
    PreAudit = 1
    Production = 2
    Hotfix = 3
    Temp1 = 4
    Temp2 = 5
    Temp3 = 6
    Temp4 = 7
    Temp5 = 8
    Test = 9
    TestIn = 10

class PurchaseStatusCode(IntEnum):
    none = 0
    Start = 1
    PublishSuccess = 2
    End = 3
    Error = 4
    DuplicateOrder = 5
    Refund = 6

class StoreType(IntEnum):
    none = 0
    GooglePlay = 1
    AppStore = 2
    OneStore = 3

class PurchasePeriodType(IntEnum):
    none = 0
    Day = 1
    Week = 2
    Month = 3

class PurchaseSourceType(IntEnum):
    none = 0
    Product = 1
    ProductMonthly = 2

class ProductCategory(IntEnum):
    none = 0
    Gem = 1
    Monthly = 2
    Package = 3

class ProductDisplayTag(IntEnum):
    none = 0
    New = 1
    Hot = 2
    Sale = 3

class BillingTransactionEndType(IntEnum):
    none = 0
    Success = 1
    Cancel = 2

class GachaRewardType(IntEnum):
    none = 0
    Eligma = 1
    Eleph = 2

class SocialMode(IntEnum):
    TITLE = 0
    LOBBY = 1
    FORMATION = 2
    STAGE_SELECT = 3
    BATTLE = 4
    POPUP = 5
    BATTLE_RESULT = 6
    BATTLE_RESULT_VICTORY = 7
    BATTLE_RESULT_DEFEAT = 8
    INVALID = 9
    TACTIC = 10
    STRATEGY = 11
    ACCONT = 12
    CAMPAIGN_STORY = 13
    CAMPAIGN_STAGE = 14
    TACTICREADY = 15

class AccountState(IntEnum):
    WaitingSignIn = 0
    Normal = 1
    Dormant = 2
    Comeback = 3
    Newbie = 4

class MessagePopupLayout(IntEnum):
    TextOnly = 0
    ImageBig = 1
    ImageSmall = 2

class MessagePopupImagePositionType(IntEnum):
    ImageFirst = 0
    TextFirst = 1

class MessagePopupButtonType(IntEnum):
    Accept = 0
    Cancel = 1
    Command = 2

class ToastType(IntEnum):
    none = 0
    Tactic_Left = 1
    Tactic_Right = 2
    Social_Center = 3
    Social_Mission = 4
    Social_Right = 5
    Notice_Center = 6

class StrategyAIType(IntEnum):
    none = 0
    Guard = 1
    Pursuit = 2

class StageDifficulty(IntEnum):
    none = 0
    Normal = 1
    Hard = 2
    VeryHard = 3

class HexaUnitGrade(IntEnum):
    Grade1 = 0
    Grade2 = 1
    Grade3 = 2
    Boss = 3

class TacticEnvironment(IntEnum):
    none = 0
    WarFog = 1

class StrategyObjectType(IntEnum):
    none = 0
    Start = 1
    Heal = 2
    Skill = 3
    StatBuff = 4
    Parcel = 5
    ParcelOneTimePerAccount = 6
    Portal = 7
    PortalOneWayEnterance = 8
    PortalOneWayExit = 9
    Observatory = 10
    Beacon = 11
    BeaconOneTime = 12
    EnemySpawn = 13
    SwitchToggle = 14
    SwitchMovableWhenToggleOff = 15
    SwitchMovableWhenToggleOn = 16

class StrategyEnvironment(IntEnum):
    none = 0
    MapFog = 1

class Tag(IntEnum):
    Furniture = 0
    MovieMania = 1
    Scientific = 2
    Military = 3
    Machine = 4
    Gamer = 5
    Cook = 6
    Farmer = 7
    Sociable = 8
    Officer = 9
    Eerie = 10
    Intellectual = 11
    Healthy = 12
    Gourmet = 13
    TreasureHunter = 14
    CraftItem = 15
    CDItem = 16
    ExpItem = 17
    SecretStone = 18
    BookItem = 19
    FavorItem = 20
    MaterialItem = 21
    Item = 22
    CraftCommitment = 23
    ExpendableItem = 24
    Equipment = 25
    EnemyLarge = 26
    Decagram = 27
    EnemySmall = 28
    EnemyMedium = 29
    EnemyXLarge = 30
    Gehenna = 31
    Millennium = 32
    Valkyrie = 33
    Hyakkiyako = 34
    RedWinter = 35
    Shanhaijing = 36
    Abydos = 37
    Trinity = 38
    Hanger = 39
    StudyRoom = 40
    ClassRoom = 41
    Library = 42
    Lobby = 43
    ShootingRange = 44
    Office = 45
    SchaleResidence = 46
    SchaleOffice = 47
    Restaurant = 48
    Laboratory = 49
    AVRoom = 50
    ArcadeCenter = 51
    Gym = 52
    Garden = 53
    Convenience = 54
    Soldiery = 55
    Lounge = 56
    SchoolBuilding = 57
    Club = 58
    Campus = 59
    SchoolYard = 60
    Plaza = 61
    StudentCouncilOffice = 62
    ClosedBuilding = 63
    Annex = 64
    Pool = 65
    AllySmall = 66
    AllyMedium = 67
    AllyLarge = 68
    AllyXLarge = 69
    Dessert = 70
    Sports = 71
    Bedding = 72
    Curios = 73
    Electronic = 74
    Toy = 75
    Reservation = 76
    Household = 77
    Horticulture = 78
    Fashion = 79
    Functional = 80
    Delicious = 81
    Freakish = 82
    MomoFriends = 83
    Music = 84
    LoveStory = 85
    Game = 86
    Girlish = 87
    Beauty = 88
    Army = 89
    Humanities = 90
    Observational = 91
    Jellyz = 92
    Detective = 93
    Roman = 94
    CuriousFellow = 95
    Mystery = 96
    Doll = 97
    Movie = 98
    Art = 99
    PureLiterature = 100
    Food = 101
    Smart = 102
    BigMeal = 103
    Simplicity = 104
    Specialized = 105
    Books = 106
    Cosmetics = 107
    Gift1 = 108
    Gift2 = 109
    F_Aru = 110
    F_Eimi = 111
    F_Haruna = 112
    F_Hihumi = 113
    F_Hina = 114
    F_Hoshino = 115
    F_Iori = 116
    F_Maki = 117
    F_Neru = 118
    F_Izumi = 119
    F_Shiroko = 120
    F_Shun = 121
    F_Sumire = 122
    F_Tsurugi = 123
    F_Akane = 124
    F_Chise = 125
    F_Akari = 126
    F_Hasumi = 127
    F_Nonomi = 128
    F_Kayoko = 129
    F_Mutsuki = 130
    F_Zunko = 131
    F_Serika = 132
    F_Tusbaki = 133
    F_Yuuka = 134
    F_Haruka = 135
    F_Asuna = 136
    F_Kotori = 137
    F_Suzumi = 138
    F_Pina = 139
    F_Aris = 140
    F_Azusa = 141
    F_Cherino = 142
    TagName0004 = 143
    TagName0005 = 144
    F_Koharu = 145
    F_Hanako = 146
    F_Midori = 147
    F_Momoi = 148
    F_Hibiki = 149
    F_Karin = 150
    F_Saya = 151
    F_Mashiro = 152
    F_Airi = 153
    F_Fuuka = 154
    F_Hanae = 155
    F_Hare = 156
    F_Utaha = 157
    F_Ayane = 158
    F_Chinatsu = 159
    F_Kotama = 160
    F_Juri = 161
    F_Serina = 162
    F_Shimiko = 163
    F_Yoshimi = 164
    TagName0009 = 165
    F_Shizuko = 166
    F_Izuna = 167
    F_Nodoka = 168
    F_Yuzu = 169
    Shield = 170
    Helmet = 171
    RedHelmet = 172
    Helicopter = 173
    RangeAttack = 174
    MeleeAttack = 175
    Sweeper = 176
    Blackmarket = 177
    Yoheki = 178
    Kaiserpmc = 179
    Crusader = 180
    Goliath = 181
    Drone = 182
    Piece = 183
    ChampionHeavyArmor = 184
    Sukeban = 185
    Arius = 186
    EnemyKotori = 187
    EnemyYuuka = 188
    KaiserpmcHeavyArmor = 189
    BlackmarketHeavyArmor = 190
    YohekiHeavyArmor = 191
    SweeperBlack = 192
    SweeperYellow = 193
    GasMaskLightArmor = 194
    GehennaFuuki = 195
    ChampionAutomata = 196
    YohekiAutomata = 197
    Automata = 198
    EnemyIori = 199
    EnemyAkari = 200
    NewAutomata = 201
    NewAutomataBlack = 202
    NewAutomataYellow = 203
    Hat = 204
    Gloves = 205
    Shoes = 206
    Bag = 207
    Badge = 208
    Hairpin = 209
    Charm = 210
    Watch = 211
    Necklace = 212
    Cafe = 213
    GameCenter = 214
    ChocolateCafe = 215
    Main = 216
    Support = 217
    Explosion = 218
    Pierce = 219
    Mystic = 220
    LightArmor = 221
    HeavyArmor = 222
    Unarmed = 223
    Cover = 224
    Uncover = 225
    AR = 226
    SR = 227
    DSG = 228
    SMG = 229
    MG = 230
    HG = 231
    GL = 232
    SG = 233
    MT = 234
    RG = 235
    Front = 236
    Middle = 237
    Back = 238
    StreetBattle_Over_A = 239
    OutdoorBattle_Over_A = 240
    IndoorBattle_Over_A = 241
    StreetBattle_Under_B = 242
    OutdoorBattle_Under_B = 243
    IndoorBattle_Under_B = 244
    Kaitenranger = 245
    Transport = 246
    Itcenter = 247
    Powerplant = 248
    SukebanSwim_SMG = 249
    SukebanSwim_MG = 250
    SukebanSwim_SR = 251
    SukebanSwim_Champion = 252
    Token_S6 = 253
    Swimsuit = 254
    WaterPlay = 255
    F_Hihumi_Swimsuit = 256
    F_Azusa_Swimsuit = 257
    F_Tsurugi_Swimsuit = 258
    F_Mashiro_Swimsuit = 259
    F_Hina_swimsuit = 260
    F_Iori_swimsuit = 261
    F_Izumi_swimsuit = 262
    F_Shiroko_RidingSuit = 263
    Church = 264
    Stronghold = 265
    Gallery = 266
    MusicRoom = 267
    Emotional = 268
    F_Shun_Kid = 269
    F_Kirino_default = 270
    F_Saya_Casual = 271
    TagName0270 = 272
    TagName0271 = 273
    TagName0272 = 274
    TagName0273 = 275
    TagName0274 = 276
    TagName0275 = 277
    TagName0276 = 278
    TagName0277 = 279
    TagName0278 = 280
    TagName0279 = 281
    TagName0280 = 282
    TagName0281 = 283
    TagName0282 = 284
    TagName0283 = 285
    TagName0284 = 286
    TagName0285 = 287
    TagName0286 = 288
    TagName0287 = 289
    TagName0288 = 290
    TagName0289 = 291
    TagName0290 = 292
    TagName0291 = 293
    TagName0292 = 294
    TagName0293 = 295
    TagName0294 = 296
    TagName0295 = 297
    TagName0296 = 298
    TagName0297 = 299
    TagName0298 = 300
    TagName0299 = 301
    TagName0300 = 302
    TagName0301 = 303
    TagName0302 = 304
    TagName0303 = 305
    TagName0304 = 306
    TagName0305 = 307
    TagName0306 = 308
    TagName0307 = 309
    TagName0308 = 310
    TagName0309 = 311
    TagName0310 = 312
    TagName0311 = 313
    TagName0312 = 314
    TagName0313 = 315
    TagName0314 = 316
    TagName0315 = 317
    TagName0316 = 318
    TagName0317 = 319
    TagName0318 = 320
    TagName0319 = 321
    TagName0320 = 322
    TagName0321 = 323
    TagName0322 = 324
    TagName0323 = 325
    TagName0324 = 326
    TagName0325 = 327
    TagName0326 = 328
    TagName0327 = 329
    TagName0328 = 330
    TagName0329 = 331
    TagName0330 = 332
    TagName0331 = 333
    TagName0332 = 334
    TagName0333 = 335
    TagName0334 = 336
    TagName0335 = 337
    TagName0336 = 338
    TagName0337 = 339
    TagName0338 = 340
    TagName0339 = 341
    TagName0340 = 342
    TagName0341 = 343
    TagName0342 = 344
    TagName0343 = 345
    TagName0344 = 346
    TagName0345 = 347
    TagName0346 = 348
    TagName0347 = 349
    TagName0348 = 350
    TagName0349 = 351
    TagName0350 = 352
    TagName0351 = 353
    TagName0352 = 354
    TagName0353 = 355
    TagName0354 = 356
    TagName0355 = 357
    TagName0356 = 358
    TagName0357 = 359
    TagName0358 = 360
    TagName0359 = 361
    TagName0360 = 362
    TagName0361 = 363
    TagName0362 = 364
    TagName0363 = 365
    TagName0364 = 366
    TagName0365 = 367
    TagName0366 = 368
    TagName0367 = 369
    TagName0368 = 370
    TagName0369 = 371
    TagName0370 = 372
    TagName0371 = 373
    TagName0372 = 374
    TagName0373 = 375
    TagName0374 = 376
    TagName0375 = 377
    TagName0376 = 378
    TagName0377 = 379
    TagName0378 = 380
    TagName0379 = 381
    TagName0380 = 382
    TagName0381 = 383
    TagName0382 = 384
    TagName0383 = 385
    TagName0384 = 386
    TagName0385 = 387
    TagName0386 = 388
    TagName0387 = 389
    TagName0388 = 390
    TagName0389 = 391
    TagName0390 = 392
    TagName0391 = 393
    TagName0392 = 394
    TagName0393 = 395
    TagName0394 = 396
    TagName0395 = 397
    TagName0396 = 398
    TagName0397 = 399
    TagName0398 = 400
    TagName0399 = 401
    TagName0400 = 402
    TagName0401 = 403
    TagName0402 = 404
    TagName0403 = 405
    TagName0404 = 406
    TagName0405 = 407
    TagName0406 = 408
    TagName0407 = 409
    TagName0408 = 410
    TagName0409 = 411
    TagName0410 = 412
    TagName0411 = 413
    TagName0412 = 414
    TagName0413 = 415
    TagName0414 = 416
    TagName0415 = 417
    TagName0416 = 418
    TagName0417 = 419
    TagName0418 = 420
    TagName0419 = 421
    TagName0420 = 422
    TagName0421 = 423
    TagName0422 = 424
    TagName0423 = 425
    TagName0424 = 426
    TagName0425 = 427
    TagName0426 = 428
    TagName0427 = 429
    TagName0428 = 430
    TagName0429 = 431
    TagName0430 = 432
    TagName0431 = 433
    TagName0432 = 434
    TagName0433 = 435
    TagName0434 = 436
    TagName0435 = 437
    TagName0436 = 438
    TagName0437 = 439
    TagName0438 = 440
    TagName0439 = 441
    TagName0440 = 442
    TagName0441 = 443
    TagName0442 = 444
    TagName0443 = 445
    TagName0444 = 446
    TagName0445 = 447
    TagName0446 = 448
    TagName0447 = 449
    TagName0448 = 450
    TagName0449 = 451
    TagName0450 = 452
    TagName0451 = 453
    TagName0452 = 454
    TagName0453 = 455
    TagName0454 = 456
    TagName0455 = 457
    TagName0456 = 458
    TagName0457 = 459
    TagName0458 = 460
    TagName0459 = 461
    TagName0460 = 462
    TagName0461 = 463
    TagName0462 = 464
    TagName0463 = 465
    TagName0464 = 466
    TagName0465 = 467
    TagName0466 = 468
    TagName0467 = 469
    TagName0468 = 470
    TagName0469 = 471
    TagName0470 = 472
    TagName0471 = 473
    TagName0472 = 474
    TagName0473 = 475
    TagName0474 = 476
    TagName0475 = 477
    TagName0476 = 478
    TagName0477 = 479
    TagName0478 = 480
    TagName0479 = 481
    TagName0480 = 482
    TagName0481 = 483
    TagName0482 = 484
    TagName0483 = 485
    TagName0484 = 486
    TagName0485 = 487
    TagName0486 = 488
    TagName0487 = 489
    TagName0488 = 490
    TagName0489 = 491
    TagName0490 = 492
    TagName0491 = 493
    TagName0492 = 494
    TagName0493 = 495
    TagName0494 = 496
    TagName0495 = 497
    TagName0496 = 498
    TagName0497 = 499
    TagName0498 = 500
    TagName0499 = 501
    TagName0500 = 502
    TagName0501 = 503
    TagName0502 = 504
    TagName0503 = 505
    TagName0504 = 506
    TagName0505 = 507
    TagName0506 = 508
    TagName0507 = 509
    TagName0508 = 510
    TagName0509 = 511
    TagName0510 = 512
    TagName0511 = 513
    TagName0512 = 514
    TagName0513 = 515
    TagName0514 = 516
    TagName0515 = 517
    TagName0516 = 518
    TagName0517 = 519
    TagName0518 = 520
    TagName0519 = 521
    TagName0520 = 522
    TagName0521 = 523
    TagName0522 = 524
    TagName0523 = 525
    TagName0524 = 526
    TagName0525 = 527
    TagName0526 = 528
    TagName0527 = 529
    TagName0528 = 530
    TagName0529 = 531
    TagName0530 = 532
    TagName0531 = 533
    TagName0532 = 534
    TagName0533 = 535
    TagName0534 = 536
    TagName0535 = 537
    TagName0536 = 538
    TagName0537 = 539
    TagName0538 = 540
    TagName0539 = 541
    TagName0540 = 542
    TagName0541 = 543
    TagName0542 = 544
    TagName0543 = 545
    TagName0544 = 546
    TagName0545 = 547
    TagName0546 = 548
    TagName0547 = 549
    TagName0548 = 550
    TagName0549 = 551
    TagName0550 = 552
    TagName0551 = 553
    TagName0552 = 554
    TagName0553 = 555
    TagName0554 = 556
    TagName0555 = 557
    TagName0556 = 558
    TagName0557 = 559
    TagName0558 = 560
    TagName0559 = 561
    TagName0560 = 562
    TagName0561 = 563
    TagName0562 = 564
    TagName0563 = 565
    TagName0564 = 566
    TagName0565 = 567
    TagName0566 = 568
    TagName0567 = 569
    TagName0568 = 570
    TagName0569 = 571
    TagName0570 = 572
    TagName0571 = 573
    TagName0572 = 574
    TagName0573 = 575
    TagName0574 = 576
    TagName0575 = 577
    TagName0576 = 578
    TagName0577 = 579
    TagName0578 = 580
    TagName0579 = 581
    TagName0580 = 582
    TagName0581 = 583
    TagName0582 = 584
    TagName0583 = 585
    TagName0584 = 586
    TagName0585 = 587
    TagName0586 = 588
    TagName0587 = 589
    TagName0588 = 590
    TagName0589 = 591
    TagName0590 = 592
    TagName0591 = 593
    TagName0592 = 594
    TagName0593 = 595
    TagName0594 = 596
    TagName0595 = 597
    TagName0596 = 598
    TagName0597 = 599
    TagName0598 = 600
    TagName0599 = 601
    TagName0600 = 602
    TagName0601 = 603
    TagName0602 = 604
    TagName0603 = 605
    TagName0604 = 606
    TagName0605 = 607
    TagName0606 = 608
    TagName0607 = 609
    TagName0608 = 610
    TagName0609 = 611
    TagName0610 = 612
    TagName0611 = 613
    TagName0612 = 614
    TagName0613 = 615
    TagName0614 = 616
    TagName0615 = 617
    TagName0616 = 618
    TagName0617 = 619
    TagName0618 = 620
    TagName0619 = 621
    TagName0620 = 622
    TagName0621 = 623
    TagName0622 = 624
    TagName0623 = 625
    TagName0624 = 626
    TagName0625 = 627
    TagName0626 = 628
    TagName0627 = 629
    TagName0628 = 630
    TagName0629 = 631
    TagName0630 = 632
    TagName0631 = 633
    TagName0632 = 634
    TagName0633 = 635
    TagName0634 = 636
    TagName0635 = 637
    TagName0636 = 638
    TagName0637 = 639
    TagName0638 = 640
    TagName0639 = 641
    TagName0640 = 642
    TagName0641 = 643
    TagName0642 = 644
    TagName0643 = 645
    TagName0644 = 646
    TagName0645 = 647
    TagName0646 = 648
    TagName0647 = 649
    TagName0648 = 650
    TagName0649 = 651
    TagName0650 = 652
    TagName0651 = 653
    TagName0652 = 654
    TagName0653 = 655
    TagName0654 = 656
    TagName0655 = 657
    TagName0656 = 658
    TagName0657 = 659
    TagName0658 = 660
    TagName0659 = 661
    TagName0660 = 662
    TagName0661 = 663
    TagName0662 = 664
    TagName0663 = 665
    TagName0664 = 666
    TagName0665 = 667
    TagName0666 = 668
    TagName0667 = 669
    TagName0668 = 670
    TagName0669 = 671
    TagName0670 = 672
    TagName0671 = 673
    TagName0672 = 674
    TagName0673 = 675
    TagName0674 = 676
    TagName0675 = 677
    TagName0676 = 678
    TagName0677 = 679
    TagName0678 = 680
    TagName0679 = 681
    TagName0680 = 682
    TagName0681 = 683
    TagName0682 = 684
    TagName0683 = 685
    TagName0684 = 686
    TagName0685 = 687
    TagName0686 = 688
    TagName0687 = 689
    TagName0688 = 690
    TagName0689 = 691
    TagName0690 = 692
    TagName0691 = 693
    TagName0692 = 694
    TagName0693 = 695
    TagName0694 = 696
    TagName0695 = 697
    TagName0696 = 698
    TagName0697 = 699
    TagName0698 = 700
    TagName0699 = 701
    TagName0700 = 702
    TagName0701 = 703
    TagName0702 = 704
    TagName0703 = 705
    TagName0704 = 706
    TagName0705 = 707
    TagName0706 = 708
    TagName0707 = 709
    TagName0708 = 710
    TagName0709 = 711
    TagName0710 = 712
    TagName0711 = 713
    TagName0712 = 714
    TagName0713 = 715
    TagName0714 = 716
    TagName0715 = 717
    TagName0716 = 718
    TagName0717 = 719
    TagName0718 = 720
    TagName0719 = 721
    TagName0720 = 722
    TagName0721 = 723
    TagName0722 = 724
    TagName0723 = 725
    TagName0724 = 726
    TagName0725 = 727
    TagName0726 = 728
    TagName0727 = 729
    TagName0728 = 730
    TagName0729 = 731
    TagName0730 = 732
    TagName0731 = 733
    TagName0732 = 734
    TagName0733 = 735
    TagName0734 = 736
    TagName0735 = 737
    TagName0736 = 738
    TagName0737 = 739
    TagName0738 = 740
    TagName0739 = 741
    TagName0740 = 742
    TagName0741 = 743
    TagName0742 = 744
    TagName0743 = 745
    TagName0744 = 746
    TagName0745 = 747
    TagName0746 = 748
    TagName0747 = 749
    TagName0748 = 750
    TagName0749 = 751
    TagName0750 = 752
    TagName0751 = 753
    TagName0752 = 754
    TagName0753 = 755
    TagName0754 = 756
    TagName0755 = 757
    TagName0756 = 758
    TagName0757 = 759
    TagName0758 = 760
    TagName0759 = 761
    TagName0760 = 762
    TagName0761 = 763
    TagName0762 = 764
    TagName0763 = 765
    TagName0764 = 766
    TagName0765 = 767
    TagName0766 = 768
    TagName0767 = 769
    TagName0768 = 770
    TagName0769 = 771
    TagName0770 = 772
    TagName0771 = 773
    TagName0772 = 774
    TagName0773 = 775
    TagName0774 = 776
    TagName0775 = 777
    TagName0776 = 778
    TagName0777 = 779
    TagName0778 = 780
    TagName0779 = 781
    TagName0780 = 782
    TagName0781 = 783
    TagName0782 = 784
    TagName0783 = 785
    TagName0784 = 786
    TagName0785 = 787
    TagName0786 = 788
    TagName0787 = 789
    TagName0788 = 790
    TagName0789 = 791
    TagName0790 = 792
    TagName0791 = 793
    TagName0792 = 794
    TagName0793 = 795
    TagName0794 = 796
    TagName0795 = 797
    TagName0796 = 798
    TagName0797 = 799
    TagName0798 = 800
    TagName0799 = 801
    TagName0800 = 802
    TagName0801 = 803
    TagName0802 = 804
    TagName0803 = 805
    TagName0804 = 806
    TagName0805 = 807
    TagName0806 = 808
    TagName0807 = 809
    TagName0808 = 810
    TagName0809 = 811
    TagName0810 = 812
    TagName0811 = 813
    TagName0812 = 814
    TagName0813 = 815
    TagName0814 = 816
    TagName0815 = 817
    TagName0816 = 818
    TagName0817 = 819
    TagName0818 = 820
    TagName0819 = 821
    TagName0820 = 822
    TagName0821 = 823
    TagName0822 = 824
    TagName0823 = 825
    TagName0824 = 826
    TagName0825 = 827
    TagName0826 = 828
    TagName0827 = 829
    TagName0828 = 830
    TagName0829 = 831
    TagName0830 = 832
    TagName0831 = 833
    TagName0832 = 834
    TagName0833 = 835
    TagName0834 = 836
    TagName0835 = 837
    TagName0836 = 838
    TagName0837 = 839
    TagName0838 = 840
    TagName0839 = 841
    TagName0840 = 842
    TagName0841 = 843
    TagName0842 = 844
    TagName0843 = 845
    TagName0844 = 846
    TagName0845 = 847
    TagName0846 = 848
    TagName0847 = 849
    TagName0848 = 850
    TagName0849 = 851
    TagName0850 = 852
    TagName0851 = 853
    TagName0852 = 854
    TagName0853 = 855
    TagName0854 = 856
    TagName0855 = 857
    TagName0856 = 858
    TagName0857 = 859
    TagName0858 = 860
    TagName0859 = 861
    TagName0860 = 862
    TagName0861 = 863
    TagName0862 = 864
    TagName0863 = 865
    TagName0864 = 866
    TagName0865 = 867
    TagName0866 = 868
    TagName0867 = 869
    TagName0868 = 870
    TagName0869 = 871
    TagName0870 = 872
    TagName0871 = 873
    TagName0872 = 874
    TagName0873 = 875
    TagName0874 = 876
    TagName0875 = 877
    TagName0876 = 878
    TagName0877 = 879
    TagName0878 = 880
    TagName0879 = 881
    TagName0880 = 882
    TagName0881 = 883
    TagName0882 = 884
    TagName0883 = 885
    TagName0884 = 886
    TagName0885 = 887
    TagName0886 = 888
    TagName0887 = 889
    TagName0888 = 890
    TagName0889 = 891
    TagName0890 = 892
    TagName0891 = 893
    TagName0892 = 894
    TagName0893 = 895
    TagName0894 = 896
    TagName0895 = 897
    TagName0896 = 898
    TagName0897 = 899
    TagName0898 = 900
    TagName0899 = 901
    TagName0900 = 902
    TagName0901 = 903
    TagName0902 = 904
    TagName0903 = 905
    TagName0904 = 906
    TagName0905 = 907
    TagName0906 = 908
    TagName0907 = 909
    TagName0908 = 910
    TagName0909 = 911
    TagName0910 = 912
    TagName0911 = 913
    TagName0912 = 914
    TagName0913 = 915
    TagName0914 = 916
    TagName0915 = 917
    TagName0916 = 918
    TagName0917 = 919
    TagName0918 = 920
    TagName0919 = 921
    TagName0920 = 922
    TagName0921 = 923
    TagName0922 = 924
    TagName0923 = 925
    TagName0924 = 926
    TagName0925 = 927
    TagName0926 = 928
    TagName0927 = 929
    TagName0928 = 930
    TagName0929 = 931
    TagName0930 = 932
    TagName0931 = 933
    TagName0932 = 934
    TagName0933 = 935
    TagName0934 = 936
    TagName0935 = 937
    TagName0936 = 938
    TagName0937 = 939
    TagName0938 = 940
    TagName0939 = 941
    TagName0940 = 942
    TagName0941 = 943
    TagName0942 = 944
    TagName0943 = 945
    TagName0944 = 946
    TagName0945 = 947
    TagName0946 = 948
    TagName0947 = 949
    TagName0948 = 950
    TagName0949 = 951
    TagName0950 = 952
    TagName0951 = 953
    TagName0952 = 954
    TagName0953 = 955
    TagName0954 = 956
    TagName0955 = 957
    TagName0956 = 958
    TagName0957 = 959
    TagName0958 = 960
    TagName0959 = 961
    TagName0960 = 962
    TagName0961 = 963
    TagName0962 = 964
    TagName0963 = 965
    TagName0964 = 966
    TagName0965 = 967
    TagName0966 = 968
    TagName0967 = 969
    TagName0968 = 970
    TagName0969 = 971
    TagName0970 = 972
    TagName0971 = 973
    TagName0972 = 974
    TagName0973 = 975
    TagName0974 = 976
    TagName0975 = 977
    TagName0976 = 978
    TagName0977 = 979
    TagName0978 = 980
    TagName0979 = 981
    TagName0980 = 982
    TagName0981 = 983
    TagName0982 = 984
    TagName0983 = 985
    TagName0984 = 986
    TagName0985 = 987
    TagName0986 = 988
    TagName0987 = 989
    TagName0988 = 990
    TagName0989 = 991
    TagName0990 = 992
    TagName0991 = 993
    TagName0992 = 994
    TagName0993 = 995
    TagName0994 = 996
    TagName0995 = 997
    TagName0996 = 998
    TagName0997 = 999
    TagName0998 = 1000
    TagName0999 = 1001
    TagName1000 = 1002
    TagName1001 = 1003
    TagName1002 = 1004
    TagName1003 = 1005
    TagName1004 = 1006
    TagName1005 = 1007
    TagName1006 = 1008
    TagName1007 = 1009
    TagName1008 = 1010
    TagName1009 = 1011
    TagName1010 = 1012
    TagName1011 = 1013
    TagName1012 = 1014
    TagName1013 = 1015
    TagName1014 = 1016
    TagName1015 = 1017
    TagName1016 = 1018
    TagName1017 = 1019
    TagName1018 = 1020
    TagName1019 = 1021
    TagName1020 = 1022
    TagName1021 = 1023
    TagName1022 = 1024
    TagName1023 = 1025
    TagName1024 = 1026
    TagName1025 = 1027
    TagName1026 = 1028
    TagName1027 = 1029
    TagName1028 = 1030
    TagName1029 = 1031
    TagName1030 = 1032
    TagName1031 = 1033
    TagName1032 = 1034
    TagName1033 = 1035
    TagName1034 = 1036
    TagName1035 = 1037
    TagName1036 = 1038
    TagName1037 = 1039
    TagName1038 = 1040
    TagName1039 = 1041
    TagName1040 = 1042
    TagName1041 = 1043
    TagName1042 = 1044
    TagName1043 = 1045
    TagName1044 = 1046
    TagName1045 = 1047
    TagName1046 = 1048
    TagName1047 = 1049
    TagName1048 = 1050
    TagName1049 = 1051
    TagName1050 = 1052
    TagName1051 = 1053
    TagName1052 = 1054
    TagName1053 = 1055
    TagName1054 = 1056
    TagName1055 = 1057
    TagName1056 = 1058
    TagName1057 = 1059
    TagName1058 = 1060
    TagName1059 = 1061
    TagName1060 = 1062
    TagName1061 = 1063
    TagName1062 = 1064
    TagName1063 = 1065
    TagName1064 = 1066
    TagName1065 = 1067
    TagName1066 = 1068
    TagName1067 = 1069
    TagName1068 = 1070
    TagName1069 = 1071
    TagName1070 = 1072
    TagName1071 = 1073
    TagName1072 = 1074
    TagName1073 = 1075
    TagName1074 = 1076
    TagName1075 = 1077
    TagName1076 = 1078
    TagName1077 = 1079
    TagName1078 = 1080
    TagName1079 = 1081
    TagName1080 = 1082
    TagName1081 = 1083
    TagName1082 = 1084
    TagName1083 = 1085
    TagName1084 = 1086
    TagName1085 = 1087
    TagName1086 = 1088
    TagName1087 = 1089
    TagName1088 = 1090
    TagName1089 = 1091
    TagName1090 = 1092
    TagName1091 = 1093
    TagName1092 = 1094
    TagName1093 = 1095
    TagName1094 = 1096
    TagName1095 = 1097
    TagName1096 = 1098
    TagName1097 = 1099
    TagName1098 = 1100
    TagName1099 = 1101
    TagName1100 = 1102
    TagName1101 = 1103
    TagName1102 = 1104
    TagName1103 = 1105
    TagName1104 = 1106
    TagName1105 = 1107
    TagName1106 = 1108
    TagName1107 = 1109
    TagName1108 = 1110
    TagName1109 = 1111
    TagName1110 = 1112
    TagName1111 = 1113
    TagName1112 = 1114
    TagName1113 = 1115
    TagName1114 = 1116
    TagName1115 = 1117
    TagName1116 = 1118
    TagName1117 = 1119
    TagName1118 = 1120
    TagName1119 = 1121
    TagName1120 = 1122
    TagName1121 = 1123
    TagName1122 = 1124
    TagName1123 = 1125
    TagName1124 = 1126
    TagName1125 = 1127
    TagName1126 = 1128
    TagName1127 = 1129
    TagName1128 = 1130
    TagName1129 = 1131
    TagName1130 = 1132
    TagName1131 = 1133
    TagName1132 = 1134
    TagName1133 = 1135
    TagName1134 = 1136
    TagName1135 = 1137
    TagName1136 = 1138
    TagName1137 = 1139
    TagName1138 = 1140
    TagName1139 = 1141
    TagName1140 = 1142
    TagName1141 = 1143
    TagName1142 = 1144
    TagName1143 = 1145
    TagName1144 = 1146
    TagName1145 = 1147
    TagName1146 = 1148
    TagName1147 = 1149
    TagName1148 = 1150
    TagName1149 = 1151
    TagName1150 = 1152
    TagName1151 = 1153
    TagName1152 = 1154
    TagName1153 = 1155
    TagName1154 = 1156
    TagName1155 = 1157
    TagName1156 = 1158
    TagName1157 = 1159
    TagName1158 = 1160
    TagName1159 = 1161
    TagName1160 = 1162
    TagName1161 = 1163
    TagName1162 = 1164
    TagName1163 = 1165
    TagName1164 = 1166
    TagName1165 = 1167
    TagName1166 = 1168
    TagName1167 = 1169
    TagName1168 = 1170
    TagName1169 = 1171
    TagName1170 = 1172
    TagName1171 = 1173
    TagName1172 = 1174
    TagName1173 = 1175
    TagName1174 = 1176
    TagName1175 = 1177
    TagName1176 = 1178
    TagName1177 = 1179
    TagName1178 = 1180
    TagName1179 = 1181
    TagName1180 = 1182
    TagName1181 = 1183
    TagName1182 = 1184
    TagName1183 = 1185
    TagName1184 = 1186
    TagName1185 = 1187
    TagName1186 = 1188
    TagName1187 = 1189
    TagName1188 = 1190
    TagName1189 = 1191
    TagName1190 = 1192
    TagName1191 = 1193
    TagName1192 = 1194
    TagName1193 = 1195
    TagName1194 = 1196
    TagName1195 = 1197
    TagName1196 = 1198
    TagName1197 = 1199
    TagName1198 = 1200
    TagName1199 = 1201
    TagName1200 = 1202
    TagName1201 = 1203
    TagName1202 = 1204
    TagName1203 = 1205
    TagName1204 = 1206
    TagName1205 = 1207
    TagName1206 = 1208
    TagName1207 = 1209
    TagName1208 = 1210
    TagName1209 = 1211
    TagName1210 = 1212
    TagName1211 = 1213
    TagName1212 = 1214
    TagName1213 = 1215
    TagName1214 = 1216
    TagName1215 = 1217
    TagName1216 = 1218
    TagName1217 = 1219
    TagName1218 = 1220
    TagName1219 = 1221
    TagName1220 = 1222
    TagName1221 = 1223
    TagName1222 = 1224
    TagName1223 = 1225
    TagName1224 = 1226
    TagName1225 = 1227
    TagName1226 = 1228
    TagName1227 = 1229
    TagName1228 = 1230
    TagName1229 = 1231
    TagName1230 = 1232
    TagName1231 = 1233
    TagName1232 = 1234
    TagName1233 = 1235
    TagName1234 = 1236
    TagName1235 = 1237
    TagName1236 = 1238
    TagName1237 = 1239
    TagName1238 = 1240
    TagName1239 = 1241
    TagName1240 = 1242
    TagName1241 = 1243
    TagName1242 = 1244
    TagName1243 = 1245
    TagName1244 = 1246
    TagName1245 = 1247
    TagName1246 = 1248
    TagName1247 = 1249
    TagName1248 = 1250
    TagName1249 = 1251
    TagName1250 = 1252
    TagName1251 = 1253
    TagName1252 = 1254
    TagName1253 = 1255
    TagName1254 = 1256
    TagName1255 = 1257
    TagName1256 = 1258
    TagName1257 = 1259
    TagName1258 = 1260
    TagName1259 = 1261
    TagName1260 = 1262
    TagName1261 = 1263
    TagName1262 = 1264
    TagName1263 = 1265
    TagName1264 = 1266
    TagName1265 = 1267
    TagName1266 = 1268
    TagName1267 = 1269
    TagName1268 = 1270
    TagName1269 = 1271
    TagName1270 = 1272
    TagName1271 = 1273
    TagName1272 = 1274
    TagName1273 = 1275
    TagName1274 = 1276
    TagName1275 = 1277
    TagName1276 = 1278
    TagName1277 = 1279
    TagName1278 = 1280
    TagName1279 = 1281
    TagName1280 = 1282
    TagName1281 = 1283
    TagName1282 = 1284
    TagName1283 = 1285
    TagName1284 = 1286
    TagName1285 = 1287
    TagName1286 = 1288
    TagName1287 = 1289
    TagName1288 = 1290
    TagName1289 = 1291
    TagName1290 = 1292
    TagName1291 = 1293
    TagName1292 = 1294
    TagName1293 = 1295
    TagName1294 = 1296
    TagName1295 = 1297
    TagName1296 = 1298
    TagName1297 = 1299
    TagName1298 = 1300
    TagName1299 = 1301
    TagName1300 = 1302
    TagName1301 = 1303
    TagName1302 = 1304
    TagName1303 = 1305
    TagName1304 = 1306
    TagName1305 = 1307
    TagName1306 = 1308
    TagName1307 = 1309
    TagName1308 = 1310
    TagName1309 = 1311
    TagName1310 = 1312
    TagName1311 = 1313
    TagName1312 = 1314
    TagName1313 = 1315
    TagName1314 = 1316
    TagName1315 = 1317
    TagName1316 = 1318
    TagName1317 = 1319
    TagName1318 = 1320
    TagName1319 = 1321
    TagName1320 = 1322
    TagName1321 = 1323
    TagName1322 = 1324
    TagName1323 = 1325
    TagName1324 = 1326
    TagName1325 = 1327
    TagName1326 = 1328
    TagName1327 = 1329
    TagName1328 = 1330
    TagName1329 = 1331
    TagName1330 = 1332
    TagName1331 = 1333
    TagName1332 = 1334
    TagName1333 = 1335
    TagName1334 = 1336
    TagName1335 = 1337
    TagName1336 = 1338
    TagName1337 = 1339
    TagName1338 = 1340
    TagName1339 = 1341
    TagName1340 = 1342
    TagName1341 = 1343
    TagName1342 = 1344
    TagName1343 = 1345
    TagName1344 = 1346
    TagName1345 = 1347
    TagName1346 = 1348
    TagName1347 = 1349
    TagName1348 = 1350
    TagName1349 = 1351
    TagName1350 = 1352
    TagName1351 = 1353
    TagName1352 = 1354
    TagName1353 = 1355
    TagName1354 = 1356
    TagName1355 = 1357
    TagName1356 = 1358
    TagName1357 = 1359
    TagName1358 = 1360
    TagName1359 = 1361
    TagName1360 = 1362
    TagName1361 = 1363
    TagName1362 = 1364
    TagName1363 = 1365
    TagName1364 = 1366
    TagName1365 = 1367
    TagName1366 = 1368
    TagName1367 = 1369
    TagName1368 = 1370
    TagName1369 = 1371
    TagName1370 = 1372
    TagName1371 = 1373
    TagName1372 = 1374
    TagName1373 = 1375
    TagName1374 = 1376
    TagName1375 = 1377
    TagName1376 = 1378
    TagName1377 = 1379
    TagName1378 = 1380
    TagName1379 = 1381
    TagName1380 = 1382
    TagName1381 = 1383
    TagName1382 = 1384
    TagName1383 = 1385
    TagName1384 = 1386
    TagName1385 = 1387
    TagName1386 = 1388
    TagName1387 = 1389
    TagName1388 = 1390
    TagName1389 = 1391
    TagName1390 = 1392
    TagName1391 = 1393
    TagName1392 = 1394
    TagName1393 = 1395
    TagName1394 = 1396
    TagName1395 = 1397
    TagName1396 = 1398
    TagName1397 = 1399
    TagName1398 = 1400
    TagName1399 = 1401
    TagName1400 = 1402
    TagName1401 = 1403
    TagName1402 = 1404
    TagName1403 = 1405
    TagName1404 = 1406
    TagName1405 = 1407
    TagName1406 = 1408
    TagName1407 = 1409
    TagName1408 = 1410
    TagName1409 = 1411
    TagName1410 = 1412
    TagName1411 = 1413
    TagName1412 = 1414
    TagName1413 = 1415
    TagName1414 = 1416
    TagName1415 = 1417
    TagName1416 = 1418
    TagName1417 = 1419
    TagName1418 = 1420
    TagName1419 = 1421
    TagName1420 = 1422
    TagName1421 = 1423
    TagName1422 = 1424
    TagName1423 = 1425
    TagName1424 = 1426
    TagName1425 = 1427
    TagName1426 = 1428
    TagName1427 = 1429
    TagName1428 = 1430
    TagName1429 = 1431
    TagName1430 = 1432
    TagName1431 = 1433
    TagName1432 = 1434
    TagName1433 = 1435
    TagName1434 = 1436
    TagName1435 = 1437
    TagName1436 = 1438
    TagName1437 = 1439
    TagName1438 = 1440
    TagName1439 = 1441
    TagName1440 = 1442
    TagName1441 = 1443
    TagName1442 = 1444
    TagName1443 = 1445
    TagName1444 = 1446
    TagName1445 = 1447
    TagName1446 = 1448
    TagName1447 = 1449
    TagName1448 = 1450
    TagName1449 = 1451
    TagName1450 = 1452
    TagName1451 = 1453
    TagName1452 = 1454
    TagName1453 = 1455
    TagName1454 = 1456
    TagName1455 = 1457
    TagName1456 = 1458
    TagName1457 = 1459
    TagName1458 = 1460
    TagName1459 = 1461
    TagName1460 = 1462
    TagName1461 = 1463
    TagName1462 = 1464
    TagName1463 = 1465
    TagName1464 = 1466
    TagName1465 = 1467
    TagName1466 = 1468
    TagName1467 = 1469
    TagName1468 = 1470
    TagName1469 = 1471
    TagName1470 = 1472
    TagName1471 = 1473
    TagName1472 = 1474
    TagName1473 = 1475
    TagName1474 = 1476
    TagName1475 = 1477
    TagName1476 = 1478
    TagName1477 = 1479
    TagName1478 = 1480
    TagName1479 = 1481
    TagName1480 = 1482
    TagName1481 = 1483
    TagName1482 = 1484
    TagName1483 = 1485
    TagName1484 = 1486
    TagName1485 = 1487
    TagName1486 = 1488
    TagName1487 = 1489
    TagName1488 = 1490
    TagName1489 = 1491
    TagName1490 = 1492
    TagName1491 = 1493
    TagName1492 = 1494
    TagName1493 = 1495
    TagName1494 = 1496
    TagName1495 = 1497
    TagName1496 = 1498
    TagName1497 = 1499
    TagName1498 = 1500
    TagName1499 = 1501
    TagName1500 = 1502
    TagName1501 = 1503
    TagName1502 = 1504
    TagName1503 = 1505
    TagName1504 = 1506
    TagName1505 = 1507
    TagName1506 = 1508
    TagName1507 = 1509
    TagName1508 = 1510
    TagName1509 = 1511
    TagName1510 = 1512
    TagName1511 = 1513
    TagName1512 = 1514
    TagName1513 = 1515
    TagName1514 = 1516
    TagName1515 = 1517
    TagName1516 = 1518
    TagName1517 = 1519
    TagName1518 = 1520
    TagName1519 = 1521
    TagName1520 = 1522
    TagName1521 = 1523
    TagName1522 = 1524
    TagName1523 = 1525
    TagName1524 = 1526
    TagName1525 = 1527
    TagName1526 = 1528
    TagName1527 = 1529
    TagName1528 = 1530
    TagName1529 = 1531
    TagName1530 = 1532
    TagName1531 = 1533
    TagName1532 = 1534
    TagName1533 = 1535
    TagName1534 = 1536
    TagName1535 = 1537
    TagName1536 = 1538
    TagName1537 = 1539
    TagName1538 = 1540
    TagName1539 = 1541
    TagName1540 = 1542
    TagName1541 = 1543
    TagName1542 = 1544
    TagName1543 = 1545
    TagName1544 = 1546
    TagName1545 = 1547
    TagName1546 = 1548
    TagName1547 = 1549
    TagName1548 = 1550
    TagName1549 = 1551
    TagName1550 = 1552
    TagName1551 = 1553
    TagName1552 = 1554
    TagName1553 = 1555
    TagName1554 = 1556
    TagName1555 = 1557
    TagName1556 = 1558
    TagName1557 = 1559
    TagName1558 = 1560
    TagName1559 = 1561
    TagName1560 = 1562
    TagName1561 = 1563
    TagName1562 = 1564
    TagName1563 = 1565
    TagName1564 = 1566
    TagName1565 = 1567
    TagName1566 = 1568
    TagName1567 = 1569
    TagName1568 = 1570
    TagName1569 = 1571
    TagName1570 = 1572
    TagName1571 = 1573
    TagName1572 = 1574
    TagName1573 = 1575
    TagName1574 = 1576
    TagName1575 = 1577
    TagName1576 = 1578
    TagName1577 = 1579
    TagName1578 = 1580
    TagName1579 = 1581
    TagName1580 = 1582
    TagName1581 = 1583
    TagName1582 = 1584
    TagName1583 = 1585
    TagName1584 = 1586
    TagName1585 = 1587
    TagName1586 = 1588
    TagName1587 = 1589
    TagName1588 = 1590
    TagName1589 = 1591
    TagName1590 = 1592
    TagName1591 = 1593
    TagName1592 = 1594
    TagName1593 = 1595
    TagName1594 = 1596
    TagName1595 = 1597
    TagName1596 = 1598
    TagName1597 = 1599
    TagName1598 = 1600
    TagName1599 = 1601
    TagName1600 = 1602
    TagName1601 = 1603
    TagName1602 = 1604
    TagName1603 = 1605
    TagName1604 = 1606
    TagName1605 = 1607
    TagName1606 = 1608
    TagName1607 = 1609
    TagName1608 = 1610
    TagName1609 = 1611
    TagName1610 = 1612
    TagName1611 = 1613
    TagName1612 = 1614
    TagName1613 = 1615
    TagName1614 = 1616
    TagName1615 = 1617
    TagName1616 = 1618
    TagName1617 = 1619
    TagName1618 = 1620
    TagName1619 = 1621
    TagName1620 = 1622
    TagName1621 = 1623
    TagName1622 = 1624
    TagName1623 = 1625
    TagName1624 = 1626
    TagName1625 = 1627
    TagName1626 = 1628
    TagName1627 = 1629
    TagName1628 = 1630
    TagName1629 = 1631
    TagName1630 = 1632
    TagName1631 = 1633
    TagName1632 = 1634
    TagName1633 = 1635
    TagName1634 = 1636
    TagName1635 = 1637
    TagName1636 = 1638
    TagName1637 = 1639
    TagName1638 = 1640
    TagName1639 = 1641
    TagName1640 = 1642
    TagName1641 = 1643
    TagName1642 = 1644
    TagName1643 = 1645
    TagName1644 = 1646
    TagName1645 = 1647
    TagName1646 = 1648
    TagName1647 = 1649
    TagName1648 = 1650
    TagName1649 = 1651
    TagName1650 = 1652
    TagName1651 = 1653
    TagName1652 = 1654
    TagName1653 = 1655
    TagName1654 = 1656
    TagName1655 = 1657
    TagName1656 = 1658
    TagName1657 = 1659
    TagName1658 = 1660
    TagName1659 = 1661
    TagName1660 = 1662
    TagName1661 = 1663
    TagName1662 = 1664
    TagName1663 = 1665
    TagName1664 = 1666
    TagName1665 = 1667
    TagName1666 = 1668
    TagName1667 = 1669
    TagName1668 = 1670
    TagName1669 = 1671
    TagName1670 = 1672
    TagName1671 = 1673
    TagName1672 = 1674
    TagName1673 = 1675
    TagName1674 = 1676
    TagName1675 = 1677
    TagName1676 = 1678
    TagName1677 = 1679
    TagName1678 = 1680
    TagName1679 = 1681
    TagName1680 = 1682
    TagName1681 = 1683
    TagName1682 = 1684
    TagName1683 = 1685
    TagName1684 = 1686
    TagName1685 = 1687
    TagName1686 = 1688
    TagName1687 = 1689
    TagName1688 = 1690
    TagName1689 = 1691
    TagName1690 = 1692
    TagName1691 = 1693
    TagName1692 = 1694
    TagName1693 = 1695
    TagName1694 = 1696
    TagName1695 = 1697
    TagName1696 = 1698
    TagName1697 = 1699
    TagName1698 = 1700
    TagName1699 = 1701
    TagName1700 = 1702
    TagName1701 = 1703
    TagName1702 = 1704
    TagName1703 = 1705
    TagName1704 = 1706
    TagName1705 = 1707
    TagName1706 = 1708
    TagName1707 = 1709
    TagName1708 = 1710
    TagName1709 = 1711
    TagName1710 = 1712
    TagName1711 = 1713
    TagName1712 = 1714
    TagName1713 = 1715
    TagName1714 = 1716
    TagName1715 = 1717
    TagName1716 = 1718
    TagName1717 = 1719
    TagName1718 = 1720
    TagName1719 = 1721
    TagName1720 = 1722
    TagName1721 = 1723
    TagName1722 = 1724
    TagName1723 = 1725
    TagName1724 = 1726
    TagName1725 = 1727
    TagName1726 = 1728
    TagName1727 = 1729
    TagName1728 = 1730
    TagName1729 = 1731
    TagName1730 = 1732
    TagName1731 = 1733
    TagName1732 = 1734
    TagName1733 = 1735
    TagName1734 = 1736
    TagName1735 = 1737
    TagName1736 = 1738
    TagName1737 = 1739
    TagName1738 = 1740
    TagName1739 = 1741
    TagName1740 = 1742
    TagName1741 = 1743
    TagName1742 = 1744
    TagName1743 = 1745
    TagName1744 = 1746
    TagName1745 = 1747
    TagName1746 = 1748
    TagName1747 = 1749
    TagName1748 = 1750
    TagName1749 = 1751
    TagName1750 = 1752
    TagName1751 = 1753
    TagName1752 = 1754
    TagName1753 = 1755
    TagName1754 = 1756
    TagName1755 = 1757
    TagName1756 = 1758
    TagName1757 = 1759
    TagName1758 = 1760
    TagName1759 = 1761
    TagName1760 = 1762
    TagName1761 = 1763
    TagName1762 = 1764
    TagName1763 = 1765
    TagName1764 = 1766
    TagName1765 = 1767
    TagName1766 = 1768
    TagName1767 = 1769
    TagName1768 = 1770
    TagName1769 = 1771
    TagName1770 = 1772
    TagName1771 = 1773
    TagName1772 = 1774
    TagName1773 = 1775
    TagName1774 = 1776
    TagName1775 = 1777
    TagName1776 = 1778
    TagName1777 = 1779
    TagName1778 = 1780
    TagName1779 = 1781
    TagName1780 = 1782
    TagName1781 = 1783
    TagName1782 = 1784
    TagName1783 = 1785
    TagName1784 = 1786
    TagName1785 = 1787
    TagName1786 = 1788
    TagName1787 = 1789
    TagName1788 = 1790
    TagName1789 = 1791
    TagName1790 = 1792
    TagName1791 = 1793
    TagName1792 = 1794
    TagName1793 = 1795
    TagName1794 = 1796
    TagName1795 = 1797
    TagName1796 = 1798
    TagName1797 = 1799
    TagName1798 = 1800
    TagName1799 = 1801
    TagName1800 = 1802
    TagName1801 = 1803
    TagName1802 = 1804
    TagName1803 = 1805
    TagName1804 = 1806
    TagName1805 = 1807
    TagName1806 = 1808
    TagName1807 = 1809
    TagName1808 = 1810
    TagName1809 = 1811
    TagName1810 = 1812
    TagName1811 = 1813
    TagName1812 = 1814
    TagName1813 = 1815
    TagName1814 = 1816
    TagName1815 = 1817
    TagName1816 = 1818
    TagName1817 = 1819
    TagName1818 = 1820
    TagName1819 = 1821
    TagName1820 = 1822
    TagName1821 = 1823
    TagName1822 = 1824
    TagName1823 = 1825
    TagName1824 = 1826
    TagName1825 = 1827
    TagName1826 = 1828
    TagName1827 = 1829
    TagName1828 = 1830
    TagName1829 = 1831
    TagName1830 = 1832
    TagName1831 = 1833
    TagName1832 = 1834
    TagName1833 = 1835
    TagName1834 = 1836
    TagName1835 = 1837
    TagName1836 = 1838
    TagName1837 = 1839
    TagName1838 = 1840
    TagName1839 = 1841
    TagName1840 = 1842
    TagName1841 = 1843
    TagName1842 = 1844
    TagName1843 = 1845
    TagName1844 = 1846
    TagName1845 = 1847
    TagName1846 = 1848
    TagName1847 = 1849
    TagName1848 = 1850
    TagName1849 = 1851
    TagName1850 = 1852
    TagName1851 = 1853
    TagName1852 = 1854
    TagName1853 = 1855
    TagName1854 = 1856
    TagName1855 = 1857
    TagName1856 = 1858
    TagName1857 = 1859
    TagName1858 = 1860
    TagName1859 = 1861
    TagName1860 = 1862
    TagName1861 = 1863
    TagName1862 = 1864
    TagName1863 = 1865
    TagName1864 = 1866
    TagName1865 = 1867
    TagName1866 = 1868
    TagName1867 = 1869
    TagName1868 = 1870
    TagName1869 = 1871
    TagName1870 = 1872
    TagName1871 = 1873
    TagName1872 = 1874
    TagName1873 = 1875
    TagName1874 = 1876
    TagName1875 = 1877
    TagName1876 = 1878
    TagName1877 = 1879
    TagName1878 = 1880
    TagName1879 = 1881
    TagName1880 = 1882
    TagName1881 = 1883
    TagName1882 = 1884
    TagName1883 = 1885
    TagName1884 = 1886
    TagName1885 = 1887
    TagName1886 = 1888
    TagName1887 = 1889
    TagName1888 = 1890
    TagName1889 = 1891
    TagName1890 = 1892
    TagName1891 = 1893
    TagName1892 = 1894
    TagName1893 = 1895
    TagName1894 = 1896
    TagName1895 = 1897
    TagName1896 = 1898
    TagName1897 = 1899
    TagName1898 = 1900
    TagName1899 = 1901
    TagName1900 = 1902
    TagName1901 = 1903
    TagName1902 = 1904
    TagName1903 = 1905
    TagName1904 = 1906
    TagName1905 = 1907
    TagName1906 = 1908
    TagName1907 = 1909
    TagName1908 = 1910
    TagName1909 = 1911
    TagName1910 = 1912
    TagName1911 = 1913
    TagName1912 = 1914
    TagName1913 = 1915
    TagName1914 = 1916
    TagName1915 = 1917
    TagName1916 = 1918
    TagName1917 = 1919
    TagName1918 = 1920
    TagName1919 = 1921
    TagName1920 = 1922
    TagName1921 = 1923
    TagName1922 = 1924
    TagName1923 = 1925
    TagName1924 = 1926
    TagName1925 = 1927
    TagName1926 = 1928
    TagName1927 = 1929
    TagName1928 = 1930
    TagName1929 = 1931
    TagName1930 = 1932
    TagName1931 = 1933
    TagName1932 = 1934
    TagName1933 = 1935
    TagName1934 = 1936
    TagName1935 = 1937
    TagName1936 = 1938
    TagName1937 = 1939
    TagName1938 = 1940
    TagName1939 = 1941
    TagName1940 = 1942
    TagName1941 = 1943
    TagName1942 = 1944
    TagName1943 = 1945
    TagName1944 = 1946
    TagName1945 = 1947
    TagName1946 = 1948
    TagName1947 = 1949
    TagName1948 = 1950
    TagName1949 = 1951
    TagName1950 = 1952
    TagName1951 = 1953
    TagName1952 = 1954
    TagName1953 = 1955
    TagName1954 = 1956
    TagName1955 = 1957
    TagName1956 = 1958
    TagName1957 = 1959
    TagName1958 = 1960
    TagName1959 = 1961
    TagName1960 = 1962
    TagName1961 = 1963
    TagName1962 = 1964
    TagName1963 = 1965
    TagName1964 = 1966
    TagName1965 = 1967
    TagName1966 = 1968
    TagName1967 = 1969
    TagName1968 = 1970
    TagName1969 = 1971
    TagName1970 = 1972
    TagName1971 = 1973
    TagName1972 = 1974
    TagName1973 = 1975
    TagName1974 = 1976
    TagName1975 = 1977
    TagName1976 = 1978
    TagName1977 = 1979
    TagName1978 = 1980
    TagName1979 = 1981
    TagName1980 = 1982
    TagName1981 = 1983
    TagName1982 = 1984
    TagName1983 = 1985
    TagName1984 = 1986
    TagName1985 = 1987
    TagName1986 = 1988
    TagName1987 = 1989
    TagName1988 = 1990
    TagName1989 = 1991
    TagName1990 = 1992
    TagName1991 = 1993
    TagName1992 = 1994
    TagName1993 = 1995
    TagName1994 = 1996
    TagName1995 = 1997
    TagName1996 = 1998
    TagName1997 = 1999
    TagName1998 = 2000
    TagName1999 = 2001
    TagName2000 = 2002
    TagName2001 = 2003
    TagName2002 = 2004
    TagName2003 = 2005
    TagName2004 = 2006
    TagName2005 = 2007
    TagName2006 = 2008
    TagName2007 = 2009
    TagName2008 = 2010
    TagName2009 = 2011
    TagName2010 = 2012
    TagName2011 = 2013
    TagName2012 = 2014
    TagName2013 = 2015
    TagName2014 = 2016
    TagName2015 = 2017
    TagName2016 = 2018
    TagName2017 = 2019
    TagName2018 = 2020
    TagName2019 = 2021
    TagName2020 = 2022
    TagName2021 = 2023
    TagName2022 = 2024
    TagName2023 = 2025
    TagName2024 = 2026
    TagName2025 = 2027
    TagName2026 = 2028
    TagName2027 = 2029
    TagName2028 = 2030
    TagName2029 = 2031
    TagName2030 = 2032
    TagName2031 = 2033
    TagName2032 = 2034
    TagName2033 = 2035
    TagName2034 = 2036
    TagName2035 = 2037
    TagName2036 = 2038
    TagName2037 = 2039
    TagName2038 = 2040
    TagName2039 = 2041
    TagName2040 = 2042
    TagName2041 = 2043
    TagName2042 = 2044
    TagName2043 = 2045
    TagName2044 = 2046
    TagName2045 = 2047
    TagName2046 = 2048
    TagName2047 = 2049
    TagName2048 = 2050
    TagName2049 = 2051
    TagName2050 = 2052
    TagName2051 = 2053
    TagName2052 = 2054
    TagName2053 = 2055
    TagName2054 = 2056
    TagName2055 = 2057
    TagName2056 = 2058
    TagName2057 = 2059
    TagName2058 = 2060
    TagName2059 = 2061
    TagName2060 = 2062
    TagName2061 = 2063
    TagName2062 = 2064
    TagName2063 = 2065
    TagName2064 = 2066
    TagName2065 = 2067
    TagName2066 = 2068
    TagName2067 = 2069
    TagName2068 = 2070
    TagName2069 = 2071
    TagName2070 = 2072
    TagName2071 = 2073
    TagName2072 = 2074
    TagName2073 = 2075
    TagName2074 = 2076
    TagName2075 = 2077
    TagName2076 = 2078
    TagName2077 = 2079
    TagName2078 = 2080
    TagName2079 = 2081
    TagName2080 = 2082
    TagName2081 = 2083
    TagName2082 = 2084
    TagName2083 = 2085
    TagName2084 = 2086
    TagName2085 = 2087
    TagName2086 = 2088
    TagName2087 = 2089
    TagName2088 = 2090
    TagName2089 = 2091
    TagName2090 = 2092
    TagName2091 = 2093
    TagName2092 = 2094
    TagName2093 = 2095
    TagName2094 = 2096
    TagName2095 = 2097
    TagName2096 = 2098
    TagName2097 = 2099
    TagName2098 = 2100
    TagName2099 = 2101
    TagName2100 = 2102
    TagName2101 = 2103
    TagName2102 = 2104
    TagName2103 = 2105
    TagName2104 = 2106
    TagName2105 = 2107
    TagName2106 = 2108
    TagName2107 = 2109
    TagName2108 = 2110
    TagName2109 = 2111
    TagName2110 = 2112
    TagName2111 = 2113
    TagName2112 = 2114
    TagName2113 = 2115
    TagName2114 = 2116
    TagName2115 = 2117
    TagName2116 = 2118
    TagName2117 = 2119
    TagName2118 = 2120
    TagName2119 = 2121
    TagName2120 = 2122
    TagName2121 = 2123
    TagName2122 = 2124
    TagName2123 = 2125
    TagName2124 = 2126
    TagName2125 = 2127
    TagName2126 = 2128
    TagName2127 = 2129
    TagName2128 = 2130
    TagName2129 = 2131
    TagName2130 = 2132
    TagName2131 = 2133
    TagName2132 = 2134
    TagName2133 = 2135
    TagName2134 = 2136
    TagName2135 = 2137
    TagName2136 = 2138
    TagName2137 = 2139
    TagName2138 = 2140
    TagName2139 = 2141
    TagName2140 = 2142
    TagName2141 = 2143
    TagName2142 = 2144
    TagName2143 = 2145
    TagName2144 = 2146
    TagName2145 = 2147
    TagName2146 = 2148
    TagName2147 = 2149
    TagName2148 = 2150
    TagName2149 = 2151
    TagName2150 = 2152
    TagName2151 = 2153
    TagName2152 = 2154
    TagName2153 = 2155
    TagName2154 = 2156
    TagName2155 = 2157
    TagName2156 = 2158
    TagName2157 = 2159
    TagName2158 = 2160
    TagName2159 = 2161
    TagName2160 = 2162
    TagName2161 = 2163
    TagName2162 = 2164
    TagName2163 = 2165
    TagName2164 = 2166
    TagName2165 = 2167
    TagName2166 = 2168
    TagName2167 = 2169
    TagName2168 = 2170
    TagName2169 = 2171
    TagName2170 = 2172
    TagName2171 = 2173
    TagName2172 = 2174
    TagName2173 = 2175
    TagName2174 = 2176
    TagName2175 = 2177
    TagName2176 = 2178
    TagName2177 = 2179
    TagName2178 = 2180
    TagName2179 = 2181
    TagName2180 = 2182
    TagName2181 = 2183
    TagName2182 = 2184
    TagName2183 = 2185
    TagName2184 = 2186
    TagName2185 = 2187
    TagName2186 = 2188
    TagName2187 = 2189
    TagName2188 = 2190
    TagName2189 = 2191
    TagName2190 = 2192
    TagName2191 = 2193
    TagName2192 = 2194
    TagName2193 = 2195
    TagName2194 = 2196
    TagName2195 = 2197
    TagName2196 = 2198
    TagName2197 = 2199
    TagName2198 = 2200
    TagName2199 = 2201
    TagName2200 = 2202
    TagName2201 = 2203
    TagName2202 = 2204
    TagName2203 = 2205
    TagName2204 = 2206
    TagName2205 = 2207
    TagName2206 = 2208
    TagName2207 = 2209
    TagName2208 = 2210
    TagName2209 = 2211
    TagName2210 = 2212
    TagName2211 = 2213
    TagName2212 = 2214
    TagName2213 = 2215
    TagName2214 = 2216
    TagName2215 = 2217
    TagName2216 = 2218
    TagName2217 = 2219
    TagName2218 = 2220
    TagName2219 = 2221
    TagName2220 = 2222
    TagName2221 = 2223
    TagName2222 = 2224
    TagName2223 = 2225
    TagName2224 = 2226
    TagName2225 = 2227
    TagName2226 = 2228
    TagName2227 = 2229
    TagName2228 = 2230
    TagName2229 = 2231
    TagName2230 = 2232
    TagName2231 = 2233
    TagName2232 = 2234
    TagName2233 = 2235
    TagName2234 = 2236
    TagName2235 = 2237
    TagName2236 = 2238
    TagName2237 = 2239
    TagName2238 = 2240
    TagName2239 = 2241
    TagName2240 = 2242
    TagName2241 = 2243
    TagName2242 = 2244
    TagName2243 = 2245
    TagName2244 = 2246
    TagName2245 = 2247
    TagName2246 = 2248
    TagName2247 = 2249
    TagName2248 = 2250
    TagName2249 = 2251
    TagName2250 = 2252
    TagName2251 = 2253
    TagName2252 = 2254
    TagName2253 = 2255
    TagName2254 = 2256
    TagName2255 = 2257
    TagName2256 = 2258
    TagName2257 = 2259
    TagName2258 = 2260
    TagName2259 = 2261
    TagName2260 = 2262
    TagName2261 = 2263
    TagName2262 = 2264
    TagName2263 = 2265
    TagName2264 = 2266
    TagName2265 = 2267
    TagName2266 = 2268
    TagName2267 = 2269
    TagName2268 = 2270
    TagName2269 = 2271
    TagName2270 = 2272
    TagName2271 = 2273
    TagName2272 = 2274
    TagName2273 = 2275
    TagName2274 = 2276
    TagName2275 = 2277
    TagName2276 = 2278
    TagName2277 = 2279
    TagName2278 = 2280
    TagName2279 = 2281
    TagName2280 = 2282
    TagName2281 = 2283
    TagName2282 = 2284
    TagName2283 = 2285
    TagName2284 = 2286
    TagName2285 = 2287
    TagName2286 = 2288
    TagName2287 = 2289
    TagName2288 = 2290
    TagName2289 = 2291
    TagName2290 = 2292
    TagName2291 = 2293
    TagName2292 = 2294
    TagName2293 = 2295
    TagName2294 = 2296
    TagName2295 = 2297
    TagName2296 = 2298
    TagName2297 = 2299
    TagName2298 = 2300
    TagName2299 = 2301
    TagName2300 = 2302
    TagName2301 = 2303
    TagName2302 = 2304
    TagName2303 = 2305
    TagName2304 = 2306
    TagName2305 = 2307
    TagName2306 = 2308
    TagName2307 = 2309
    TagName2308 = 2310
    TagName2309 = 2311
    TagName2310 = 2312
    TagName2311 = 2313
    TagName2312 = 2314
    TagName2313 = 2315
    TagName2314 = 2316
    TagName2315 = 2317
    TagName2316 = 2318
    TagName2317 = 2319
    TagName2318 = 2320
    TagName2319 = 2321
    TagName2320 = 2322
    TagName2321 = 2323
    TagName2322 = 2324
    TagName2323 = 2325
    TagName2324 = 2326
    TagName2325 = 2327
    TagName2326 = 2328
    TagName2327 = 2329
    TagName2328 = 2330
    TagName2329 = 2331
    TagName2330 = 2332
    TagName2331 = 2333
    TagName2332 = 2334
    TagName2333 = 2335
    TagName2334 = 2336
    TagName2335 = 2337
    TagName2336 = 2338
    TagName2337 = 2339
    TagName2338 = 2340
    TagName2339 = 2341
    TagName2340 = 2342
    TagName2341 = 2343
    TagName2342 = 2344
    TagName2343 = 2345
    TagName2344 = 2346
    TagName2345 = 2347
    TagName2346 = 2348
    TagName2347 = 2349
    TagName2348 = 2350
    TagName2349 = 2351
    TagName2350 = 2352
    TagName2351 = 2353
    TagName2352 = 2354
    TagName2353 = 2355
    TagName2354 = 2356
    TagName2355 = 2357
    TagName2356 = 2358
    TagName2357 = 2359
    TagName2358 = 2360
    TagName2359 = 2361
    TagName2360 = 2362
    TagName2361 = 2363
    TagName2362 = 2364
    TagName2363 = 2365
    TagName2364 = 2366
    TagName2365 = 2367
    TagName2366 = 2368
    TagName2367 = 2369
    TagName2368 = 2370
    TagName2369 = 2371
    TagName2370 = 2372
    TagName2371 = 2373
    TagName2372 = 2374
    TagName2373 = 2375
    TagName2374 = 2376
    TagName2375 = 2377
    TagName2376 = 2378
    TagName2377 = 2379
    TagName2378 = 2380
    TagName2379 = 2381
    TagName2380 = 2382
    TagName2381 = 2383
    TagName2382 = 2384
    TagName2383 = 2385
    TagName2384 = 2386
    TagName2385 = 2387
    TagName2386 = 2388
    TagName2387 = 2389
    TagName2388 = 2390
    TagName2389 = 2391
    TagName2390 = 2392
    TagName2391 = 2393
    TagName2392 = 2394
    TagName2393 = 2395
    TagName2394 = 2396
    TagName2395 = 2397
    TagName2396 = 2398
    TagName2397 = 2399
    TagName2398 = 2400
    TagName2399 = 2401
    TagName2400 = 2402
    TagName2401 = 2403
    TagName2402 = 2404
    TagName2403 = 2405
    TagName2404 = 2406
    TagName2405 = 2407
    TagName2406 = 2408
    TagName2407 = 2409
    TagName2408 = 2410
    TagName2409 = 2411
    TagName2410 = 2412
    TagName2411 = 2413
    TagName2412 = 2414
    TagName2413 = 2415
    TagName2414 = 2416
    TagName2415 = 2417
    TagName2416 = 2418
    TagName2417 = 2419
    TagName2418 = 2420
    TagName2419 = 2421
    TagName2420 = 2422
    TagName2421 = 2423
    TagName2422 = 2424
    TagName2423 = 2425
    TagName2424 = 2426
    TagName2425 = 2427
    TagName2426 = 2428
    TagName2427 = 2429
    TagName2428 = 2430
    TagName2429 = 2431
    TagName2430 = 2432
    TagName2431 = 2433
    TagName2432 = 2434
    TagName2433 = 2435
    TagName2434 = 2436
    TagName2435 = 2437
    TagName2436 = 2438
    TagName2437 = 2439
    TagName2438 = 2440
    TagName2439 = 2441
    TagName2440 = 2442
    TagName2441 = 2443
    TagName2442 = 2444
    TagName2443 = 2445
    TagName2444 = 2446
    TagName2445 = 2447
    TagName2446 = 2448
    TagName2447 = 2449
    TagName2448 = 2450
    TagName2449 = 2451
    TagName2450 = 2452
    TagName2451 = 2453
    TagName2452 = 2454
    TagName2453 = 2455
    TagName2454 = 2456
    TagName2455 = 2457
    TagName2456 = 2458
    TagName2457 = 2459
    TagName2458 = 2460
    TagName2459 = 2461
    TagName2460 = 2462
    TagName2461 = 2463
    TagName2462 = 2464
    TagName2463 = 2465
    TagName2464 = 2466
    TagName2465 = 2467
    TagName2466 = 2468
    TagName2467 = 2469
    TagName2468 = 2470
    TagName2469 = 2471
    TagName2470 = 2472
    TagName2471 = 2473
    TagName2472 = 2474
    TagName2473 = 2475
    TagName2474 = 2476
    TagName2475 = 2477
    TagName2476 = 2478
    TagName2477 = 2479
    TagName2478 = 2480
    TagName2479 = 2481
    TagName2480 = 2482
    TagName2481 = 2483
    TagName2482 = 2484
    TagName2483 = 2485
    TagName2484 = 2486
    TagName2485 = 2487
    TagName2486 = 2488
    TagName2487 = 2489
    TagName2488 = 2490
    TagName2489 = 2491
    TagName2490 = 2492
    TagName2491 = 2493
    TagName2492 = 2494
    TagName2493 = 2495
    TagName2494 = 2496
    TagName2495 = 2497
    TagName2496 = 2498
    TagName2497 = 2499
    TagName2498 = 2500
    TagName2499 = 2501
    TagName2500 = 2502
    TagName2501 = 2503
    TagName2502 = 2504
    TagName2503 = 2505
    TagName2504 = 2506
    TagName2505 = 2507
    TagName2506 = 2508
    TagName2507 = 2509
    TagName2508 = 2510
    TagName2509 = 2511
    TagName2510 = 2512
    TagName2511 = 2513
    TagName2512 = 2514
    TagName2513 = 2515
    TagName2514 = 2516
    TagName2515 = 2517
    TagName2516 = 2518
    TagName2517 = 2519
    TagName2518 = 2520
    TagName2519 = 2521
    TagName2520 = 2522
    TagName2521 = 2523
    TagName2522 = 2524
    TagName2523 = 2525
    TagName2524 = 2526
    TagName2525 = 2527
    TagName2526 = 2528
    TagName2527 = 2529
    TagName2528 = 2530
    TagName2529 = 2531
    TagName2530 = 2532
    TagName2531 = 2533
    TagName2532 = 2534
    TagName2533 = 2535
    TagName2534 = 2536
    TagName2535 = 2537
    TagName2536 = 2538
    TagName2537 = 2539
    TagName2538 = 2540
    TagName2539 = 2541
    TagName2540 = 2542
    TagName2541 = 2543
    TagName2542 = 2544
    TagName2543 = 2545
    TagName2544 = 2546
    TagName2545 = 2547
    TagName2546 = 2548
    TagName2547 = 2549
    TagName2548 = 2550
    TagName2549 = 2551
    TagName2550 = 2552
    TagName2551 = 2553
    TagName2552 = 2554
    TagName2553 = 2555
    TagName2554 = 2556
    TagName2555 = 2557
    TagName2556 = 2558
    TagName2557 = 2559
    TagName2558 = 2560
    TagName2559 = 2561
    TagName2560 = 2562
    TagName2561 = 2563
    TagName2562 = 2564
    TagName2563 = 2565
    TagName2564 = 2566
    TagName2565 = 2567
    TagName2566 = 2568
    TagName2567 = 2569
    TagName2568 = 2570
    TagName2569 = 2571
    TagName2570 = 2572
    TagName2571 = 2573
    TagName2572 = 2574
    TagName2573 = 2575
    TagName2574 = 2576
    TagName2575 = 2577
    TagName2576 = 2578
    TagName2577 = 2579
    TagName2578 = 2580
    TagName2579 = 2581
    TagName2580 = 2582
    TagName2581 = 2583
    TagName2582 = 2584
    TagName2583 = 2585
    TagName2584 = 2586
    TagName2585 = 2587
    TagName2586 = 2588
    TagName2587 = 2589
    TagName2588 = 2590
    TagName2589 = 2591
    TagName2590 = 2592
    TagName2591 = 2593
    TagName2592 = 2594
    TagName2593 = 2595
    TagName2594 = 2596
    TagName2595 = 2597
    TagName2596 = 2598
    TagName2597 = 2599
    TagName2598 = 2600
    TagName2599 = 2601
    TagName2600 = 2602
    TagName2601 = 2603
    TagName2602 = 2604
    TagName2603 = 2605
    TagName2604 = 2606
    TagName2605 = 2607
    TagName2606 = 2608
    TagName2607 = 2609
    TagName2608 = 2610
    TagName2609 = 2611
    TagName2610 = 2612
    TagName2611 = 2613
    TagName2612 = 2614
    TagName2613 = 2615
    TagName2614 = 2616
    TagName2615 = 2617
    TagName2616 = 2618
    TagName2617 = 2619
    TagName2618 = 2620
    TagName2619 = 2621
    TagName2620 = 2622
    TagName2621 = 2623
    TagName2622 = 2624
    TagName2623 = 2625
    TagName2624 = 2626
    TagName2625 = 2627
    TagName2626 = 2628
    TagName2627 = 2629
    TagName2628 = 2630
    TagName2629 = 2631
    TagName2630 = 2632
    TagName2631 = 2633
    TagName2632 = 2634
    TagName2633 = 2635
    TagName2634 = 2636
    TagName2635 = 2637
    TagName2636 = 2638
    TagName2637 = 2639
    TagName2638 = 2640
    TagName2639 = 2641
    TagName2640 = 2642
    TagName2641 = 2643
    TagName2642 = 2644
    TagName2643 = 2645
    TagName2644 = 2646
    TagName2645 = 2647
    TagName2646 = 2648
    TagName2647 = 2649
    TagName2648 = 2650
    TagName2649 = 2651
    TagName2650 = 2652
    TagName2651 = 2653
    TagName2652 = 2654
    TagName2653 = 2655
    TagName2654 = 2656
    TagName2655 = 2657
    TagName2656 = 2658
    TagName2657 = 2659
    TagName2658 = 2660
    TagName2659 = 2661
    TagName2660 = 2662
    TagName2661 = 2663
    TagName2662 = 2664
    TagName2663 = 2665
    TagName2664 = 2666
    TagName2665 = 2667
    TagName2666 = 2668
    TagName2667 = 2669
    TagName2668 = 2670
    TagName2669 = 2671
    TagName2670 = 2672
    TagName2671 = 2673
    TagName2672 = 2674
    TagName2673 = 2675
    TagName2674 = 2676
    TagName2675 = 2677
    TagName2676 = 2678
    TagName2677 = 2679
    TagName2678 = 2680
    TagName2679 = 2681
    TagName2680 = 2682
    TagName2681 = 2683
    TagName2682 = 2684
    TagName2683 = 2685
    TagName2684 = 2686
    TagName2685 = 2687
    TagName2686 = 2688
    TagName2687 = 2689
    TagName2688 = 2690
    TagName2689 = 2691
    TagName2690 = 2692
    TagName2691 = 2693
    TagName2692 = 2694
    TagName2693 = 2695
    TagName2694 = 2696
    TagName2695 = 2697
    TagName2696 = 2698
    TagName2697 = 2699
    TagName2698 = 2700
    TagName2699 = 2701
    TagName2700 = 2702
    TagName2701 = 2703
    TagName2702 = 2704
    TagName2703 = 2705
    TagName2704 = 2706
    TagName2705 = 2707
    TagName2706 = 2708
    TagName2707 = 2709
    TagName2708 = 2710
    TagName2709 = 2711
    TagName2710 = 2712
    TagName2711 = 2713
    TagName2712 = 2714
    TagName2713 = 2715
    TagName2714 = 2716
    TagName2715 = 2717
    TagName2716 = 2718
    TagName2717 = 2719
    TagName2718 = 2720
    TagName2719 = 2721
    TagName2720 = 2722
    TagName2721 = 2723
    TagName2722 = 2724
    TagName2723 = 2725
    TagName2724 = 2726
    TagName2725 = 2727
    TagName2726 = 2728
    TagName2727 = 2729
    TagName2728 = 2730
    TagName2729 = 2731
    TagName2730 = 2732
    TagName2731 = 2733
    TagName2732 = 2734
    TagName2733 = 2735
    TagName2734 = 2736
    TagName2735 = 2737
    TagName2736 = 2738
    TagName2737 = 2739
    TagName2738 = 2740
    TagName2739 = 2741
    TagName2740 = 2742
    TagName2741 = 2743
    TagName2742 = 2744
    TagName2743 = 2745
    TagName2744 = 2746
    TagName2745 = 2747
    TagName2746 = 2748
    TagName2747 = 2749
    TagName2748 = 2750
    TagName2749 = 2751
    TagName2750 = 2752
    TagName2751 = 2753
    TagName2752 = 2754
    TagName2753 = 2755
    TagName2754 = 2756
    TagName2755 = 2757
    TagName2756 = 2758
    TagName2757 = 2759
    TagName2758 = 2760
    TagName2759 = 2761
    TagName2760 = 2762
    TagName2761 = 2763
    TagName2762 = 2764
    TagName2763 = 2765
    TagName2764 = 2766
    TagName2765 = 2767
    TagName2766 = 2768
    TagName2767 = 2769
    TagName2768 = 2770
    TagName2769 = 2771
    TagName2770 = 2772
    TagName2771 = 2773
    TagName2772 = 2774
    TagName2773 = 2775
    TagName2774 = 2776
    TagName2775 = 2777
    TagName2776 = 2778
    TagName2777 = 2779
    TagName2778 = 2780
    TagName2779 = 2781
    TagName2780 = 2782
    TagName2781 = 2783
    TagName2782 = 2784
    TagName2783 = 2785
    TagName2784 = 2786
    TagName2785 = 2787
    TagName2786 = 2788
    TagName2787 = 2789
    TagName2788 = 2790
    TagName2789 = 2791
    TagName2790 = 2792
    TagName2791 = 2793
    TagName2792 = 2794
    TagName2793 = 2795
    TagName2794 = 2796
    TagName2795 = 2797
    TagName2796 = 2798
    TagName2797 = 2799
    TagName2798 = 2800
    TagName2799 = 2801
    TagName2800 = 2802
    TagName2801 = 2803
    TagName2802 = 2804
    TagName2803 = 2805
    TagName2804 = 2806
    TagName2805 = 2807
    TagName2806 = 2808
    TagName2807 = 2809
    TagName2808 = 2810
    TagName2809 = 2811
    TagName2810 = 2812
    TagName2811 = 2813
    TagName2812 = 2814
    TagName2813 = 2815
    TagName2814 = 2816
    TagName2815 = 2817
    TagName2816 = 2818
    TagName2817 = 2819
    TagName2818 = 2820
    TagName2819 = 2821
    TagName2820 = 2822
    TagName2821 = 2823
    TagName2822 = 2824
    TagName2823 = 2825
    TagName2824 = 2826
    TagName2825 = 2827
    TagName2826 = 2828
    TagName2827 = 2829
    TagName2828 = 2830
    TagName2829 = 2831
    TagName2830 = 2832
    TagName2831 = 2833
    TagName2832 = 2834
    TagName2833 = 2835
    TagName2834 = 2836
    TagName2835 = 2837
    TagName2836 = 2838
    TagName2837 = 2839
    TagName2838 = 2840
    TagName2839 = 2841
    TagName2840 = 2842
    TagName2841 = 2843
    TagName2842 = 2844
    TagName2843 = 2845
    TagName2844 = 2846
    TagName2845 = 2847
    TagName2846 = 2848
    TagName2847 = 2849
    TagName2848 = 2850
    TagName2849 = 2851
    TagName2850 = 2852
    TagName2851 = 2853
    TagName2852 = 2854
    TagName2853 = 2855
    TagName2854 = 2856
    TagName2855 = 2857
    TagName2856 = 2858
    TagName2857 = 2859
    TagName2858 = 2860
    TagName2859 = 2861
    TagName2860 = 2862
    TagName2861 = 2863
    TagName2862 = 2864
    TagName2863 = 2865
    TagName2864 = 2866
    TagName2865 = 2867
    TagName2866 = 2868
    TagName2867 = 2869
    TagName2868 = 2870
    TagName2869 = 2871
    TagName2870 = 2872
    TagName2871 = 2873
    TagName2872 = 2874
    TagName2873 = 2875
    TagName2874 = 2876
    TagName2875 = 2877
    TagName2876 = 2878
    TagName2877 = 2879
    TagName2878 = 2880
    TagName2879 = 2881
    TagName2880 = 2882
    TagName2881 = 2883
    TagName2882 = 2884
    TagName2883 = 2885
    TagName2884 = 2886
    TagName2885 = 2887
    TagName2886 = 2888
    TagName2887 = 2889
    TagName2888 = 2890
    TagName2889 = 2891
    TagName2890 = 2892
    TagName2891 = 2893
    TagName2892 = 2894
    TagName2893 = 2895
    TagName2894 = 2896
    TagName2895 = 2897
    TagName2896 = 2898
    TagName2897 = 2899
    TagName2898 = 2900
    TagName2899 = 2901
    TagName2900 = 2902
    TagName2901 = 2903
    TagName2902 = 2904
    TagName2903 = 2905
    TagName2904 = 2906
    TagName2905 = 2907
    TagName2906 = 2908
    TagName2907 = 2909
    TagName2908 = 2910
    TagName2909 = 2911
    TagName2910 = 2912
    TagName2911 = 2913
    TagName2912 = 2914
    TagName2913 = 2915
    TagName2914 = 2916
    TagName2915 = 2917
    TagName2916 = 2918
    TagName2917 = 2919
    TagName2918 = 2920
    TagName2919 = 2921
    TagName2920 = 2922
    TagName2921 = 2923
    TagName2922 = 2924
    TagName2923 = 2925
    TagName2924 = 2926
    TagName2925 = 2927
    TagName2926 = 2928
    TagName2927 = 2929
    TagName2928 = 2930
    TagName2929 = 2931
    TagName2930 = 2932
    TagName2931 = 2933
    TagName2932 = 2934
    TagName2933 = 2935
    TagName2934 = 2936
    TagName2935 = 2937
    TagName2936 = 2938
    TagName2937 = 2939
    TagName2938 = 2940
    TagName2939 = 2941
    TagName2940 = 2942
    TagName2941 = 2943
    TagName2942 = 2944
    TagName2943 = 2945
    TagName2944 = 2946
    TagName2945 = 2947
    TagName2946 = 2948
    TagName2947 = 2949
    TagName2948 = 2950
    TagName2949 = 2951
    TagName2950 = 2952
    TagName2951 = 2953
    TagName2952 = 2954
    TagName2953 = 2955
    TagName2954 = 2956
    TagName2955 = 2957
    TagName2956 = 2958
    TagName2957 = 2959
    TagName2958 = 2960
    TagName2959 = 2961
    TagName2960 = 2962
    TagName2961 = 2963
    TagName2962 = 2964
    TagName2963 = 2965
    TagName2964 = 2966
    TagName2965 = 2967
    TagName2966 = 2968
    TagName2967 = 2969
    TagName2968 = 2970
    TagName2969 = 2971
    TagName2970 = 2972
    TagName2971 = 2973
    TagName2972 = 2974
    TagName2973 = 2975
    TagName2974 = 2976
    TagName2975 = 2977
    TagName2976 = 2978
    TagName2977 = 2979
    TagName2978 = 2980
    TagName2979 = 2981
    TagName2980 = 2982
    TagName2981 = 2983
    TagName2982 = 2984
    TagName2983 = 2985
    TagName2984 = 2986
    TagName2985 = 2987
    TagName2986 = 2988
    TagName2987 = 2989
    TagName2988 = 2990
    TagName2989 = 2991
    TagName2990 = 2992
    TagName2991 = 2993
    TagName2992 = 2994
    TagName2993 = 2995
    TagName2994 = 2996
    TagName2995 = 2997
    TagName2996 = 2998
    TagName2997 = 2999
    TagName2998 = 3000
    TagName2999 = 3001
    TagName3000 = 3002

class Club(IntEnum):
    none = 0
    Engineer = 1
    CleanNClearing = 2
    KnightsHospitaller = 3
    IndeGEHENNA = 4
    IndeMILLENNIUM = 5
    IndeHyakkiyako = 6
    IndeShanhaijing = 7
    IndeTrinity = 8
    FoodService = 9
    Countermeasure = 10
    BookClub = 11
    MatsuriOffice = 12
    GourmetClub = 13
    HoukagoDessert = 14
    RedwinterSecretary = 15
    Schale = 16
    TheSeminar = 17
    AriusSqud = 18
    Justice = 19
    Fuuki = 20
    Kohshinjo68 = 21
    Meihuayuan = 22
    SisterHood = 23
    GameDev = 24
    anzenkyoku = 25
    RemedialClass = 26
    SPTF = 27
    TrinityVigilance = 28
    Veritas = 29
    TrainingClub = 30
    Onmyobu = 31
    Shugyobu = 32
    Endanbou = 33
    NinpoKenkyubu = 34
    Class227 = 35

class GroundNodeType(IntEnum):
    none = 0
    WalkAble = 1
    JumpAble = 2
    TSSOnly = 3
    NotWalkAble = 2147483647

