<div align="center">

# Blue Archive Asset Downloader 

鏈」鐩彲浠ヤ粠涓嶅悓鏈嶅姟鍣ㄤ笅杞藉苟鎻愬彇纰ц摑妗ｆ鐨勭礌鏉愶紝鐜版敮鎻翠腑鍥芥湇銆佸浗闄呮湇銆佹棩鏈湇銆?
</div>


## 涓昏鍔熻兘

- **澶氭湇鍔″櫒鏀寔**锛氬彲浠庝腑鍥?钄氳摑妗ｆ)銆佸浗闄?Blue Archive)銆佹棩鏈?銉栥儷銉笺偄銉笺偒銈ゃ儢)涓変釜鏈嶅姟鍣ㄤ笅杞界礌鏉愩€?
<!-- - **璧勬簮瑙ｅ紑**锛氬湪鏃ユ湰鏈嶅姟鍣ㄤ腑鍖呭惈鍑犱箮瀹屾暣鐨勬敮鎸併€?-->
<!-- - **CN 闃舵鎴愭灉**锛氬綋鍓?`download --region cn`銆乣sync --region cn`銆乣relation build --region cn` 宸插彲鐢紱`--advanced-search` 浠嶆湭寮€鏀俱€?-->
<!-- - **JP 闃舵鎴愭灉**锛氬綋鍓?`download --region jp`銆乣sync --region jp`銆乣relation build --region jp` 宸插彲鐢紱`--advanced-search` 浠嶆湭寮€鏀俱€?-->


## 璧勬簮绫诲瀷

涓嬭浇鐨勬枃浠剁被鍨嬪寘鎷細

- Bundle
- Media
- Table

<!-- 鎻愬彇鐨勬枃浠剁被鍨嬪寘鎷細

- Bundle(浠匤P)
- Media
- Table(浠匤P) -->

#### **娉ㄦ剰**锛氬敖绠￠儴鍒嗗尯鍩熸敮鎸佷笅杞戒笉鍚岀増鏈殑璧勬簮锛屼絾鏄绋嬪簭涓嶄繚璇佽兘澶熸彁鍙栬繃鏃剁増鏈殑璧勬簮鏂囦欢銆?

## 鐜瑕佹眰

- Windows/Linux
- Python 3.10 鎴栨洿楂樼増鏈?
<!-- - [.NET8/.NET9 SDK](https://dotnet.microsoft.com/download)(鎻愬彇table鎴栦娇鐢ㄩ珮绾ф绱㈡椂蹇呴』瀹夎锛涙柊 dumper backend 浼樺厛浣跨敤 .NET9)  -->

## 鍏堝喅鏉′欢

璇风‘淇濆凡瀹夎 Python锛屽苟瀹夎蹇呰鐨勫簱锛?

```shell
uv sync
```

鎴栬€咃細

```shell
pip install -e .
```

## 浣跨敤璇存槑
鍛戒护缁撴瀯濡備笅锛?

```shell
ba-downloader <subcommand> [options]
python -m ba_downloader <subcommand> [options]
```

瀛愬懡浠わ細

<!-- - `ba-downloader sync [options]`: 涓嬭浇骞惰В寮€鍏ㄩ儴鍐呭 -->
- `ba-downloader download [options]`: 涓嬭浇鍏ㄩ儴鍐呭
<!-- - `ba-downloader extract [options]`: 瑙ｅ紑宸蹭笅杞界殑鍐呭 -->
<!-- - `ba-downloader relation build [options]`: 鏋勫缓瑙掕壊淇℃伅琛?-->

浣跨敤涓嬪垪鍛戒护杩愯瀹屾暣涓嬭浇涓庢彁鍙栨祦绋嬶紙绀轰緥锛夛細

```shell
ba-downloader sync --region gl
```

鎴栬€咃紝浣跨敤浠ヤ笅鍛戒护浠呬笅杞借祫婧愯€屼笉杩涜鎻愬彇锛堢ず渚嬶級锛?

```shell
ba-downloader download --region jp
```

涔熷彲浠ヤ娇鐢ㄦā鍧楀叆鍙ｏ細

```shell
python -m ba_downloader sync --region jp
```


## **鍩烘湰鍙傛暟**
**`*`** :**蹇呴€夌殑閫夐」**
| 鍙傛暟                       | 缂?nbsp;鍐?| 璇存槑                                                                           | 榛樿鍊?            | 绀轰緥                          |
| -------------------------- | ---------- | ------------------------------------------------------------------------------ | ------------------ | ----------------------------- |
| **`--region`**`*`          | `-r`       | **鏈嶅姟鍣ㄥ尯鍩?*锛歚cn`锛堜腑鍥斤級銆乣gl`锛堝浗闄咃級銆乣jp`锛堟棩鏈級                       | 鏃?                | `-r jp`                       |
| `--threads`                | `-t`       | **鍚屾椂涓嬭浇鎴栬В鍘嬬殑绾跨▼鏁?*                                                     | `20`               | `-t 50`                       |
| `--version`                | `-v`       | **闇€瑕佷笅杞界殑璧勬簮鐗堟湰鍙?*锛堜粎 GL 鐢熸晥锛?                                        | 鏃?                | `-v 1.2.3`                    |
| `--platform`               | `-p`       | **璧勬簮鎵€灞炲钩鍙?*锛歚windows`銆乣android`銆乣ios`锛堜粎 JP 鐢熸晥锛?                   | `android`          | `-p windows`                  |
| `--raw-dir`                | `-rd`      | **鎸囧畾鏈鐞嗘枃浠剁殑浣嶇疆**                                                       | `"RawData"`        | `-rd raw_folder`              |
| `--extract-dir`            | `-ed`      | **鎸囧畾宸叉彁鍙栨枃浠剁殑浣嶇疆**                                                       | `"Extracted"`      | `-ed output_folder`           |
| `--temp-dir`               | `-td`      | **鎸囧畾涓存椂鏂囦欢鐨勪綅缃?*                                                         | `"Temp"`           | `-td temp_dir`                |
| `--extract-while-download` | `-ewd`     | **鏄惁鍦ㄤ笅杞芥椂渚挎彁鍙栨枃浠?*锛堜粎 `sync` 鍙敤锛涜緝鎱紝鍦ㄨ祫婧愭暟閲忚緝澶氭椂閰屾儏浣跨敤锛?  | `False`            | `--extract-while-download`    |
| `--resource-type`          | `-rt`      | **璧勬簮绫诲瀷**锛歚table`銆乣media`銆乣bundle`銆乣all`                                | `all`              | `--resource-type media table` |
| `--proxy`                  | `-px`      | **璁剧疆 HTTP 浠ｇ悊**                                                             | 鏃狅紙浣跨敤绯荤粺浠ｇ悊锛?| `-px http://127.0.0.1:8080`   |
| `--max-retries`            | `-mr`      | **涓嬭浇澶辫触鏃剁殑鏈€澶ч噸璇曟鏁?*                                                   | `5`                | `--max-retries 3`             |
| `--search`                 | `-s`       | **鏅€氭绱?*锛屾寚瀹氶渶瑕佹绱㈠苟涓嬭浇鐨勬枃浠跺叧閿瘝锛堜粎 `sync` 涓?`download` 鍙敤锛?  |
| `--advanced-search`        | `-as`      | **楂樼骇妫€绱?*锛屾寚瀹氳鑹插叧閿瘝锛堜粎 `sync` 鍙敤锛涘綋鍓嶄粎 GL 鏀寔锛岄渶瑕?.NET 鐜锛?|

**(CN鏈嶅姟鍣ㄧ洰鍓嶄笉鏀寔楂樼骇妫€绱?楂樼骇妫€绱㈡敮鎸佺殑妫€绱㈡潯浠讹細**
- `[*]` **瑙掕壊鍚嶇О**
- `cv` **澹颁紭**
- `age` **骞撮緞**
- `height` **韬珮**
- `birthday` **鐢熸棩**
- `illustrator` **浣滅敾鑰?*
- `school` **鎵€灞炲鍥?*锛堝寘鎷絾涓嶉檺浜庯級锛?
  - `RedWinter`銆乣Trinity`銆乣Gehenna`銆乣Abydos`銆乣Millennium`銆乣Arius`
  - `Shanhaijing`銆乣Valkyrie`銆乣WildHunt`銆乣SRT`銆乣SCHALE`銆乣ETC`
  - `Tokiwadai`銆乣Sakugawa`
- `club` **鎵€灞炵ぞ鍥?*锛堝寘鎷絾涓嶉檺浜庯級锛?
  - `Engineer`銆乣CleanNClearing`銆乣KnightsHospitaller`銆乣IndeGEHENNA`
  - `IndeMILLENNIUM`銆乣IndeHyakkiyako`銆乣IndeShanhaijing`銆乣IndeTrinity`
  - `FoodService`銆乣Countermeasure`銆乣BookClub`銆乣MatsuriOffice` ...

---
#### 骞朵笖锛屽湪涓嶅悓鐨勬湇鍔″櫒涓害鏀寔涓嶅悓鐨勫悕绉版绱㈡柟寮忥紝鍏蜂綋鍐呭璇峰弬鐓<Region>CharacterRelation.json`銆?
- 绀轰緥锛?
  > sync
  >```sh
  >ba-downloader sync --region gl -as 璨濋泤鐗归噷姒?喔⑧腹喙€喔∴赴 ibuki
  >```

  <!--
  > japan
  >```sh
  >ba-downloader sync --region jp -as yume 鐧惧悎鍦掋偦銈ゃ偄 順胳嫓雲?cv=灏忓€夊敮 height=153 birthday=2/19 illustrator=YutokaMizu school=Arius club=GameDev
  >```
  -->

  > package name only
  >```sh
  >ba-downloader sync --region jp -s aris ch0070 shiroko
  >```


## 杈撳嚭
- `Temp`: 瀛樺偍涓存椂鏂囦欢鎴栭潪涓昏鏂囦欢銆傚锛欰pk鏂囦欢绛夈€?
- `RawData`: 瀛樺偍缁忕敱Catalog涓嬭浇鐨勬枃浠躲€傚锛欱undle銆丮edia銆乀able绛夈€?
- `Extracted`: 瀛樺偍宸叉彁鍙栫殑鏂囦欢銆傚锛欱undle銆丮edia銆乀able涓嶥umps绛夈€?
<!-- - `CharacterRelation.json`: 瑙掕壊淇℃伅锛屽彲閫氳繃 `ba-downloader relation build --region <region>` 鐢熸垚銆?-->

JP 榛樿鐩綍浼氭寜骞冲彴闅旂锛?
- **渚嬶細**`--platform android`: `JP_Android_RawData` / `JP_Android_Extracted` / `JP_Android_Temp`

绀轰緥锛?

```shell
ba-downloader download --region jp --platform windows
```


## 浣跨敤椤荤煡
- `--platform` 浠呭 JP 鐢熸晥锛岀敤浜庢寚瀹?JP 骞冲彴鐨勮祫婧愶細
  - 鍚屾椂褰卞搷 JP 榛樿杈撳嚭鐩綍鍓嶇紑锛屼緥濡?`JP_Windows_RawData`銆?
- JP鐨凙PK鏂囦欢鏉ヨ嚜浜嶢PKPure锛屽湪PlayStore宸茬粡鏇存柊鍚庯紝APKPure鍙兘闇€瑕佷竴浜涙椂闂存潵鍚屾鐗堟湰锛屽悗缁紑鏀惧畼鏂?PC 鐗堣В鏋愭敮鎸併€?
- 褰撳悇鏈嶅姟鍣ㄥ浜庣淮鎶ゆ椂闂存椂锛屽彲鑳戒細鏃犳硶鑾峰彇璧勬簮鐩綍銆?
- 鍦ㄦ煇浜涘湴鍖哄彲鑳介渶瑕佷娇鐢ㄤ唬鐞嗘湇鍔″櫒浠ヤ笅杞界壒瀹氭湇鍔″櫒鐨勬父鎴忚祫婧愩€?
- Bundle鏂囦欢鐨勬彁鍙栧熀浜嶶nityPy锛屽甯屾湜鏇村姞璇︾粏鐨勫唴瀹硅浣跨敤[AssetRipper](https://github.com/AssetRipper/AssetRipper)鎴朳AssetStudio](https://github.com/Perfare/AssetStudio)
<!-- - JP 褰撳墠鏀寔 `download --region jp`銆乣sync --region jp`銆乣relation build --region jp`锛汮P `--advanced-search` 浠嶆殏涓嶅彲鐢ㄣ€?-->

## 缁存姢璇存槑
寮€鍙戙€侀潤鎬佹鏌ャ€乨umper backend銆佸瓙妯″潡涓庡彂鐗堟祦绋嬭鍙傞槄 [docs/development.md](docs/development.md)銆?

## TODO
- `v2.0.1`
  - 瀹屽杽涓夋湇涓嬭浇娴佺▼锛圕N / GL / JP锛?
- `v2.0.2`
  - 瀹屽杽 JP 瑙ｅ紑锛堥渶瑕佸瘑閽ワ紝鑰屽瘑閽ヤ綅浜庢湇鍔″櫒锛?
  - 鍩轰簬 `dump.cs` annotation tree 鐨?MemoryPack 
  - CN metadata 瑙ｅ紑
- `v2.0.3`
  - 鏂?Bundle 瑙ｅ紑鍣?
  
## 鍏充簬椤圭洰
Blue Archive Asset Downloader v2.0.0.
鉁?鎶€鏈敮鎸侊細Codex 鉁?

鏈」鐩噰鐢?[MIT 璁稿彲璇乚(LICENSE)銆?

閮ㄥ垎鍐呭鍙傜収鑷細
- [Blue-Archive---Asset-Downloader](https://github.com/K0lb3/Blue-Archive---Asset-Downloader)
- [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)

## 鍏嶈矗澹版槑 / Disclaimer
璇ヤ粨搴撲粎渚涘涔犲拰灞曠ず鐢ㄩ€旓紝涓嶆墭绠′换浣曞疄闄呰祫婧愩€傝娉ㄦ剰锛屾墍鏈夐€氳繃鏈」鐩笅杞界殑鍐呭鍧囧簲浠呯敤浜庡悎娉曞拰姝ｅ綋鐨勭洰鐨勩€傚紑鍙戣€呬笉瀵逛换浣曚汉鍥犱娇鐢ㄦ湰椤圭洰鑰屽彲鑳藉紩鍙戠殑鐩存帴鎴栭棿鎺ョ殑鎹熷け銆佹崯瀹炽€佹硶寰嬭矗浠绘垨鍏朵粬鍚庢灉鎵挎媴浠讳綍璐ｄ换銆傜敤鎴峰湪浣跨敤鏈」鐩椂闇€鑷鎵挎媴椋庨櫓锛屽苟纭繚閬靛畧鎵€鏈夌浉鍏虫硶寰嬫硶瑙勩€傚鏋滄湁浜轰娇鐢ㄦ湰椤圭洰浠庝簨浠讳綍鏈粡鎺堟潈鎴栭潪娉曠殑娲诲姩锛屽紑鍙戣€呭姝や笉鎵挎媴浠讳綍璐ｄ换銆傜敤鎴峰簲瀵硅嚜韬殑琛屼负璐熻矗锛屽苟浜嗚В浣跨敤鏈」鐩彲鑳藉甫鏉ョ殑浠讳綍椋庨櫓銆?

This project is intended solely for educational and demonstrative purposes and does not provide any actual resources. Please note that all content downloaded through this project should only be used for legal and legitimate purposes. The developers are not liable for any direct or indirect loss, damage, legal liability, or other consequences that may arise from the use of this project. Users assume all risks associated with the use of this project and must ensure compliance with all relevant laws and regulations. If anyone uses this project for any unauthorized or illegal activities, the developers bear no responsibility. Users are responsible for their own actions and should understand the risks involved in using this project.

鈥滆敋钃濇。妗堚€濇槸涓婃捣鏄熷暩缃戠粶绉戞妧鏈夐檺鍏徃鐨勬敞鍐屽晢鏍囷紝鐗堟潈鎵€鏈夈€?

銆屻儢銉兗銈兗銈偆銉栥€嶃伅鏍紡浼氱ぞYostar銇櫥閷插晢妯欍仹銇欍€傝憲浣滄ī銇仚銇广仸淇濇湁銇曘倢銇︺亜銇俱仚銆?

"Blue Archive" is a registered trademark of NEXON Korea Corp. & NEXON GAMES Co., Ltd. All rights reserved.

