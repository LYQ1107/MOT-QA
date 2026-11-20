# A/B 成对差异样例

先列按 qa_id 排序的测试题，每维度每方向最多5条；不足时另列开发集补充，并注明最终不足数。保留完整冻结轨迹文本和两个模型原始输出。

| 维度 | 方向 | 测试集可用 | 测试选取 | 开发集补充 | 全集仍不足5条 |
|---|---|---:|---:|---:|---:|
| Count | B_correct_A_wrong | 43 | 5 | 0 | 0 |
| Count | B_wrong_A_correct | 14 | 5 | 0 | 0 |
| R/D | B_correct_A_wrong | 12 | 5 | 0 | 0 |
| R/D | B_wrong_A_correct | 14 | 5 | 0 | 0 |
| X-Order | B_correct_A_wrong | 22 | 5 | 0 | 0 |
| X-Order | B_wrong_A_correct | 31 | 5 | 0 | 0 |
| Order | B_correct_A_wrong | 3 | 3 | 0 | 2 |
| Order | B_wrong_A_correct | 4 | 4 | 1 | 0 |
| ReID | B_correct_A_wrong | 0 | 0 | 0 | 5 |
| ReID | B_wrong_A_correct | 2 | 2 | 0 | 3 |

## Count / B_correct_A_wrong / 02c6e7fb0c96

范围：test；可表达：False；视频：perception_test_video_2934。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "02c6e7fb0c96",
  "video_id": "perception_test_video_2934",
  "format": "numerical",
  "question": "How many times does the white paper change abruptly in the video?"
}
```

真值：`2`。A解析：`None`；B解析：`2`。

A 原始输出：

```text
1
```

B 原始输出：

```text
2
```

完整轨迹文本：

```text
[Tracking results] query="white paper"  video_length=18.6s  tracker_fps=5
Track 4 (mean_conf=0.72)
  visible: 0.8-0.8s | 9.0-18.4s
  first_seen: 0.8s at (0.24, 0.57)   last_seen: 18.4s at (0.41, 0.66)
  gaps: 0.8-9.0s (last pos (0.24, 0.57))
Track 7 (mean_conf=0.84)
  visible: 0.8-0.8s | 2.8-8.8s
  first_seen: 0.8s at (0.23, 0.50)   last_seen: 8.8s at (0.29, 0.35)
  gaps: 0.8-2.8s (last pos (0.23, 0.50))
Track 14 (mean_conf=0.51)
  visible: 9.8-18.4s
  first_seen: 9.8s at (0.03, 0.57)   last_seen: 18.4s at (0.13, 0.60)
  gaps: none
Track 0 (mean_conf=0.69)
  visible: 0.0-2.6s
  first_seen: 0.0s at (0.23, 0.42)   last_seen: 2.6s at (0.25, 0.38)
  gaps: none
Track 6 (mean_conf=0.24)
  visible: 0.8-0.8s | 2.2-2.6s
  first_seen: 0.8s at (0.35, 0.57)   last_seen: 2.6s at (0.36, 0.56)
  gaps: 0.8-2.2s (last pos (0.35, 0.57))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 3 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_correct_A_wrong / 05c3f3343d9f

范围：test；可表达：False；视频：charades_CJ0U1。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "05c3f3343d9f",
  "video_id": "charades_CJ0U1",
  "format": "numerical",
  "question": "How many times does the refrigerator change abruptly in the video?"
}
```

真值：`2`。A解析：`None`；B解析：`2`。

A 原始输出：

```text
0
```

B 原始输出：

```text
2
```

完整轨迹文本：

```text
[Tracking results] query="refrigerator"  video_length=29.6s  tracker_fps=5
Track 0 (mean_conf=0.57)
  visible: 0.0-21.4s
  first_seen: 0.0s at (0.55, 0.53)   last_seen: 21.4s at (0.45, 0.52)
  gaps: none
Track 11 (mean_conf=0.35)
  visible: 20.4-20.4s | 21.6-26.0s
  first_seen: 20.4s at (0.40, 0.50)   last_seen: 26.0s at (0.31, 0.50)
  gaps: 20.4-21.6s (last pos (0.40, 0.50))
Track 25 (mean_conf=0.29)
  visible: 21.6-25.2s | 26.0-26.0s
  first_seen: 21.6s at (0.42, 0.50)   last_seen: 26.0s at (0.41, 0.50)
  gaps: 25.2-26.0s (last pos (0.43, 0.50))
Track 24 (mean_conf=0.24)
  visible: 22.8-22.8s | 24.8-29.2s
  first_seen: 22.8s at (0.50, 0.50)   last_seen: 29.2s at (0.50, 0.50)
  gaps: 22.8-24.8s (last pos (0.50, 0.50))
Track 36 (mean_conf=0.29)
  visible: 26.2-29.4s
  first_seen: 26.2s at (0.44, 0.50)   last_seen: 29.4s at (0.47, 0.50)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 16 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_correct_A_wrong / 08b887d08161

范围：test；可表达：True；视频：charades_CDNV7。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "08b887d08161",
  "video_id": "charades_CDNV7",
  "format": "numerical",
  "question": "How many times does the silver table leg get fully hidden in the video?"
}
```

真值：`2`。A解析：`None`；B解析：`2`。

A 原始输出：

```text
1
```

B 原始输出：

```text
2
```

完整轨迹文本：

```text
[Tracking results] query="silver table leg"  video_length=29.8s  tracker_fps=5
Track 0 (mean_conf=0.41)
  visible: 0.0-17.4s | 20.0-20.4s | 22.4-23.0s | 24.8-29.6s
  first_seen: 0.0s at (0.62, 0.74)   last_seen: 29.6s at (0.28, 0.70)
  gaps: 17.4-20.0s (last pos (0.76, 0.69)) | 20.4-22.4s (last pos (0.96, 0.72)) | 23.0-24.8s (last pos (0.83, 0.72))
Track 1 (mean_conf=0.24)
  visible: 0.0-1.4s | 3.0-7.0s | 7.6-7.6s | 8.2-11.2s | 21.4-21.6s
  first_seen: 0.0s at (0.21, 0.80)   last_seen: 21.6s at (0.23, 0.87)
  gaps: 1.4-3.0s (last pos (0.02, 0.90)) | 7.0-7.6s (last pos (0.28, 0.83)) | 7.6-8.2s (last pos (0.32, 0.82)) | 11.2-21.4s (last pos (0.04, 0.93))
Track 31 (mean_conf=0.29)
  visible: 13.8-16.6s | 17.6-19.8s
  first_seen: 13.8s at (0.12, 0.92)   last_seen: 19.8s at (0.28, 0.79)
  gaps: 16.6-17.6s (last pos (0.32, 0.83))
Track 20 (mean_conf=0.24)
  visible: 4.6-4.8s | 6.0-10.2s | 12.6-12.6s | 13.4-13.4s
  first_seen: 4.6s at (0.02, 0.86)   last_seen: 13.4s at (0.28, 0.81)
  gaps: 4.8-6.0s (last pos (0.01, 0.85)) | 10.2-12.6s (last pos (0.09, 0.82)) | 12.6-13.4s (last pos (0.22, 0.89))
Track 70 (mean_conf=0.24)
  visible: 24.0-27.2s | 28.8-29.6s
  first_seen: 24.0s at (0.46, 0.80)   last_seen: 29.6s at (0.10, 0.80)
  gaps: 27.2-28.8s (last pos (0.08, 0.80))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 29 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_correct_A_wrong / 120b8c0c180e

范围：test；可表达：False；视频：perception_test_video_7067。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "120b8c0c180e",
  "video_id": "perception_test_video_7067",
  "format": "numerical",
  "question": "How many times does the clear glass bowl change abruptly in the video?"
}
```

真值：`2`。A解析：`None`；B解析：`2`。

A 原始输出：

```text
0
```

B 原始输出：

```text
2
```

完整轨迹文本：

```text
[Tracking results] query="clear glass bowl"  video_length=23.4s  tracker_fps=5
Track 4 (mean_conf=0.83)
  visible: 2.8-14.4s | 15.6-15.6s | 16.6-20.6s | 21.2-21.4s
  first_seen: 2.8s at (0.37, 0.57)   last_seen: 21.4s at (0.37, 0.59)
  gaps: 14.4-15.6s (last pos (0.38, 0.57)) | 15.6-16.6s (last pos (0.38, 0.57)) | 20.6-21.2s (last pos (0.38, 0.58))
Track 1 (mean_conf=0.78)
  visible: 0.0-0.0s | 0.6-2.6s | 10.2-11.0s | 11.8-11.8s | 12.4-12.4s | 14.6-18.8s | 19.6-20.0s | 20.8-21.0s | 21.6-23.2s
  first_seen: 0.0s at (0.37, 0.56)   last_seen: 23.2s at (0.37, 0.60)
  gaps: 0.0-0.6s (last pos (0.37, 0.56)) | 2.6-10.2s (last pos (0.40, 0.57)) | 11.0-11.8s (last pos (0.39, 0.57)) | 11.8-12.4s (last pos (0.39, 0.58)) | 12.4-14.6s (last pos (0.39, 0.57)) | 18.8-19.6s (last pos (0.38, 0.58)) | 20.0-20.8s (last pos (0.37, 0.58)) | 21.0-21.6s (last pos (0.37, 0.59))
Track 0 (mean_conf=0.50)
  visible: 0.0-1.0s | 2.4-3.4s
  first_seen: 0.0s at (0.41, 0.56)   last_seen: 3.4s at (0.41, 0.57)
  gaps: 1.0-2.4s (last pos (0.42, 0.56))
Track 2 (mean_conf=0.22)
  visible: 0.6-1.0s
  first_seen: 0.6s at (0.70, 0.57)   last_seen: 1.0s at (0.70, 0.57)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.

```

## Count / B_correct_A_wrong / 15f31e2572de

范围：test；可表达：False；视频：charades_D0Q6H。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "15f31e2572de",
  "video_id": "charades_D0Q6H",
  "format": "numerical",
  "question": "How many times does the black shoe rack change abruptly in the video?"
}
```

真值：`2`。A解析：`None`；B解析：`2`。

A 原始输出：

```text
0
```

B 原始输出：

```text
2
```

完整轨迹文本：

```text
[Tracking results] query="black shoe rack"  video_length=30.6s  tracker_fps=5
Track 22 (mean_conf=0.67)
  visible: 3.2-5.8s | 7.2-30.4s
  first_seen: 3.2s at (0.06, 0.71)   last_seen: 30.4s at (0.25, 0.50)
  gaps: 5.8-7.2s (last pos (0.21, 0.60))
Track 30 (mean_conf=0.51)
  visible: 5.8-7.0s | 7.6-8.0s
  first_seen: 5.8s at (0.21, 0.70)   last_seen: 8.0s at (0.21, 0.50)
  gaps: 7.0-7.6s (last pos (0.19, 0.60))
Track 4 (mean_conf=0.41)
  visible: 0.0-1.4s
  first_seen: 0.0s at (0.71, 0.50)   last_seen: 1.4s at (0.73, 0.51)
  gaps: none
Track 15 (mean_conf=0.35)
  visible: 1.8-2.8s | 11.6-11.8s
  first_seen: 1.8s at (0.76, 0.55)   last_seen: 11.8s at (0.91, 0.44)
  gaps: 2.8-11.6s (last pos (0.81, 0.69))
Track 1 (mean_conf=0.32)
  visible: 0.0-0.4s | 1.6-2.6s
  first_seen: 0.0s at (0.73, 0.56)   last_seen: 2.6s at (0.82, 0.50)
  gaps: 0.4-1.6s (last pos (0.73, 0.55))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 11 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_wrong_A_correct / 0ef023cdb6f2

范围：test；可表达：True；视频：charades_3P8NL。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "0ef023cdb6f2",
  "video_id": "charades_3P8NL",
  "format": "numerical",
  "question": "How many times does the hand come back into view in the video?"
}
```

真值：`2`。A解析：`2`；B解析：`None`。

A 原始输出：

```text
2
```

B 原始输出：

```text
1
```

完整轨迹文本：

```text
[Tracking results] query="hand"  video_length=31.2s  tracker_fps=5
Track 1 (mean_conf=0.87)
  visible: 0.0-10.0s | 10.6-12.0s | 15.6-15.6s | 17.4-17.6s | 18.6-21.4s | 22.8-25.8s | 26.8-27.6s | 28.8-29.0s
  first_seen: 0.0s at (0.28, 0.50)   last_seen: 29.0s at (0.36, 0.73)
  gaps: 10.0-10.6s (last pos (0.69, 0.35)) | 12.0-15.6s (last pos (0.38, 0.53)) | 15.6-17.4s (last pos (0.49, 0.63)) | 17.6-18.6s (last pos (0.26, 0.65)) | 21.4-22.8s (last pos (0.36, 0.70)) | 25.8-26.8s (last pos (0.23, 0.64)) | 27.6-28.8s (last pos (0.46, 0.71))
Track 14 (mean_conf=0.69)
  visible: 11.2-11.4s | 12.8-13.6s | 15.6-20.0s | 20.8-20.8s | 21.6-22.8s | 23.4-24.4s | 26.0-30.0s
  first_seen: 11.2s at (0.78, 0.77)   last_seen: 30.0s at (0.57, 0.82)
  gaps: 11.4-12.8s (last pos (0.79, 0.77)) | 13.6-15.6s (last pos (0.75, 0.75)) | 20.0-20.8s (last pos (0.56, 0.79)) | 20.8-21.6s (last pos (0.58, 0.82)) | 22.8-23.4s (last pos (0.54, 0.81)) | 24.4-26.0s (last pos (0.55, 0.83))
Track 0 (mean_conf=0.88)
  visible: 0.0-8.0s
  first_seen: 0.0s at (0.53, 0.60)   last_seen: 8.0s at (0.83, 0.57)
  gaps: none
Track 6 (mean_conf=0.80)
  visible: 8.2-10.0s | 10.6-11.0s | 11.8-12.6s | 14.4-14.4s | 15.4-15.8s | 17.8-17.8s | 18.4-18.4s | 22.2-22.2s | 26.0-26.0s | 29.8-30.4s
  first_seen: 8.2s at (0.98, 0.75)   last_seen: 30.4s at (0.06, 0.62)
  gaps: 10.0-10.6s (last pos (0.77, 0.76)) | 11.0-11.8s (last pos (0.73, 0.77)) | 12.6-14.4s (last pos (0.71, 0.75)) | 14.4-15.4s (last pos (0.73, 0.69)) | 15.8-17.8s (last pos (0.14, 0.52)) | 17.8-18.4s (last pos (0.11, 0.60)) | 18.4-22.2s (last pos (0.08, 0.59)) | 22.2-26.0s (last pos (0.11, 0.48)) | 26.0-29.8s (last pos (0.12, 0.59))
Track 2 (mean_conf=0.33)
  visible: 0.0-6.2s | 6.8-10.2s
  first_seen: 0.0s at (0.80, 0.98)   last_seen: 10.2s at (0.81, 0.97)
  gaps: 6.2-6.8s (last pos (0.80, 0.96))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 27 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_wrong_A_correct / 1e1c2ae1c7d6

范围：test；可表达：True；视频：perception_test_video_588。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "1e1c2ae1c7d6",
  "video_id": "perception_test_video_588",
  "format": "numerical",
  "question": "How many times does the small potato come back into view in the video?"
}
```

真值：`3`。A解析：`3`；B解析：`None`。

A 原始输出：

```text
3
```

B 原始输出：

```text
1
```

完整轨迹文本：

```text
[Tracking results] query="small potato"  video_length=34.4s  tracker_fps=5
Track 22 (mean_conf=0.74)
  visible: 17.4-31.6s | 32.6-34.2s
  first_seen: 17.4s at (0.42, 0.48)   last_seen: 34.2s at (0.37, 0.54)
  gaps: 31.6-32.6s (last pos (0.37, 0.54))
Track 0 (mean_conf=0.74)
  visible: 0.0-15.2s | 17.2-17.2s
  first_seen: 0.0s at (0.41, 0.48)   last_seen: 17.2s at (0.61, 0.62)
  gaps: 15.2-17.2s (last pos (0.41, 0.48))
Track 4 (mean_conf=0.29)
  visible: 1.8-1.8s | 15.4-17.2s | 22.6-22.6s | 31.8-32.4s
  first_seen: 1.8s at (0.61, 0.45)   last_seen: 32.4s at (0.55, 0.46)
  gaps: 1.8-15.4s (last pos (0.61, 0.45)) | 17.2-22.6s (last pos (0.55, 0.46)) | 22.6-31.8s (last pos (0.55, 0.46))
Track 6 (mean_conf=0.21)
  visible: 1.8-1.8s | 15.4-17.2s
  first_seen: 1.8s at (0.39, 0.20)   last_seen: 17.2s at (0.39, 0.20)
  gaps: 1.8-15.4s (last pos (0.39, 0.20))
Track 10 (mean_conf=0.22)
  visible: 15.4-16.8s | 32.0-32.4s
  first_seen: 15.4s at (0.56, 0.26)   last_seen: 32.4s at (0.56, 0.26)
  gaps: 16.8-32.0s (last pos (0.55, 0.26))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 7 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_wrong_A_correct / 41b71b1ff744

范围：test；可表达：True；视频：charades_E0AEN。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "41b71b1ff744",
  "video_id": "charades_E0AEN",
  "format": "numerical",
  "question": "How many times does the book on the bed come back into view in the video?"
}
```

真值：`2`。A解析：`2`；B解析：`None`。

A 原始输出：

```text
2
```

B 原始输出：

```text
1
```

完整轨迹文本：

```text
[Tracking results] query="book on the bed"  video_length=45.4s  tracker_fps=5
Track 0 (mean_conf=0.20)
  visible: 3.2-3.2s | 13.2-13.2s | 13.8-14.8s
  first_seen: 3.2s at (0.73, 0.92)   last_seen: 14.8s at (0.60, 0.74)
  gaps: 3.2-13.2s (last pos (0.73, 0.92)) | 13.2-13.8s (last pos (0.73, 0.92))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.

```

## Count / B_wrong_A_correct / 46b07245afc8

范围：test；可表达：False；视频：perception_test_video_552。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "46b07245afc8",
  "video_id": "perception_test_video_552",
  "format": "numerical",
  "question": "How many times does the pomegranate get partly hidden in the video?"
}
```

真值：`2`。A解析：`2`；B解析：`None`。

A 原始输出：

```text
2
```

B 原始输出：

```text
1
```

完整轨迹文本：

```text
[Tracking results] query="pomegranate"  video_length=24.6s  tracker_fps=5
Track 5 (mean_conf=0.62)
  visible: 2.6-18.0s | 19.4-19.4s
  first_seen: 2.6s at (0.89, 0.24)   last_seen: 19.4s at (0.75, 0.46)
  gaps: 18.0-19.4s (last pos (0.76, 0.47))
Track 0 (mean_conf=0.76)
  visible: 0.0-2.4s
  first_seen: 0.0s at (0.76, 0.90)   last_seen: 2.4s at (0.88, 0.68)
  gaps: none
Track 18 (mean_conf=0.24)
  visible: 14.8-16.2s | 17.8-18.0s | 19.4-19.4s | 20.2-20.2s
  first_seen: 14.8s at (0.68, 0.22)   last_seen: 20.2s at (0.56, 0.32)
  gaps: 16.2-17.8s (last pos (0.60, 0.30)) | 18.0-19.4s (last pos (0.57, 0.29)) | 19.4-20.2s (last pos (0.56, 0.29))
Track 25 (mean_conf=0.23)
  visible: 16.4-16.4s | 17.0-17.4s
  first_seen: 16.4s at (0.56, 0.28)   last_seen: 17.4s at (0.57, 0.29)
  gaps: 16.4-17.0s (last pos (0.56, 0.28))
Track 1 (mean_conf=0.32)
  visible: 2.4-2.4s
  first_seen: 2.4s at (0.73, 0.75)   last_seen: 2.4s at (0.73, 0.75)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 5 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Count / B_wrong_A_correct / 504663bac5a0

范围：test；可表达：True；视频：perception_test_video_3618。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "504663bac5a0",
  "video_id": "perception_test_video_3618",
  "format": "numerical",
  "question": "How many times does the glass skull come back into view in the video?"
}
```

真值：`2`。A解析：`2`；B解析：`None`。

A 原始输出：

```text
2
```

B 原始输出：

```text
1
```

完整轨迹文本：

```text
[Tracking results] query="glass skull"  video_length=20.2s  tracker_fps=5
Track 0 (mean_conf=0.55)
  visible: 0.0-4.2s | 5.2-11.6s | 12.4-20.0s
  first_seen: 0.0s at (0.37, 0.30)   last_seen: 20.0s at (0.24, 0.25)
  gaps: 4.2-5.2s (last pos (0.46, 0.28)) | 11.6-12.4s (last pos (0.41, 0.30))
Track 58 (mean_conf=0.33)
  visible: 12.6-20.0s
  first_seen: 12.6s at (0.57, 0.19)   last_seen: 20.0s at (0.44, 0.17)
  gaps: none
Track 12 (mean_conf=0.29)
  visible: 4.4-4.8s | 10.8-10.8s | 12.4-12.4s | 13.0-20.0s
  first_seen: 4.4s at (0.77, 0.55)   last_seen: 20.0s at (0.59, 0.53)
  gaps: 4.8-10.8s (last pos (0.62, 0.53)) | 10.8-12.4s (last pos (0.50, 0.57)) | 12.4-13.0s (last pos (0.76, 0.54))
Track 35 (mean_conf=0.30)
  visible: 5.0-10.6s
  first_seen: 5.0s at (0.60, 0.17)   last_seen: 10.6s at (0.47, 0.15)
  gaps: none
Track 34 (mean_conf=0.27)
  visible: 5.0-10.4s | 11.0-11.0s | 11.8-12.2s
  first_seen: 5.0s at (0.86, 0.54)   last_seen: 12.2s at (0.62, 0.54)
  gaps: 10.4-11.0s (last pos (0.63, 0.55)) | 11.0-11.8s (last pos (0.65, 0.56))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 17 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_correct_A_wrong / 0e9e33c81d1d

范围：test；可表达：True；视频：charades_6B328。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "0e9e33c81d1d",
  "video_id": "charades_6B328",
  "format": "sp",
  "question": "Before striped socks comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "striped socks left the frame before coming back",
  "statement_B": "striped socks was fully blocked before coming back"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="striped socks"  video_length=30.6s  tracker_fps=5
Track 0 (mean_conf=0.56)
  visible: 0.0-30.4s
  first_seen: 0.0s at (0.50, 0.80)   last_seen: 30.4s at (0.48, 0.80)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.

```

## R/D / B_correct_A_wrong / 1924c14f48a6

范围：test；可表达：True；视频：charades_FRSBQ。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "1924c14f48a6",
  "video_id": "charades_FRSBQ",
  "format": "sp",
  "question": "Before red patterned curtain comes back into view, was it fully blocked or did it left the frame?",
  "statement_A": "red patterned curtain left the frame before coming back",
  "statement_B": "red patterned curtain was fully blocked before coming back"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="red patterned curtain"  video_length=32.0s  tracker_fps=5
Track 1 (mean_conf=0.43)
  visible: 0.0-6.6s | 7.4-13.0s
  first_seen: 0.0s at (0.73, 0.36)   last_seen: 13.0s at (0.81, 0.40)
  gaps: 6.6-7.4s (last pos (0.83, 0.35))
Track 32 (mean_conf=0.37)
  visible: 18.0-18.0s | 20.2-20.2s | 22.2-22.4s | 23.0-31.8s
  first_seen: 18.0s at (0.76, 0.45)   last_seen: 31.8s at (0.70, 0.42)
  gaps: 18.0-20.2s (last pos (0.76, 0.45)) | 20.2-22.2s (last pos (0.76, 0.45)) | 22.4-23.0s (last pos (0.81, 0.46))
Track 28 (mean_conf=0.35)
  visible: 22.2-22.4s | 23.0-30.0s | 30.6-31.8s
  first_seen: 22.2s at (0.81, 0.42)   last_seen: 31.8s at (0.70, 0.47)
  gaps: 22.4-23.0s (last pos (0.81, 0.42)) | 30.0-30.6s (last pos (0.68, 0.43))
Track 10 (mean_conf=0.43)
  visible: 8.4-14.6s
  first_seen: 8.4s at (0.83, 0.35)   last_seen: 14.6s at (0.94, 0.34)
  gaps: none
Track 9 (mean_conf=0.35)
  visible: 4.8-6.0s | 6.8-8.0s | 17.2-17.2s | 18.0-22.0s
  first_seen: 4.8s at (0.79, 0.40)   last_seen: 22.0s at (0.88, 0.45)
  gaps: 6.0-6.8s (last pos (0.83, 0.39)) | 8.0-17.2s (last pos (0.85, 0.37)) | 17.2-18.0s (last pos (0.89, 0.42))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 28 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_correct_A_wrong / 3a4d09c7aa6d

范围：test；可表达：True；视频：charades_WI6NB。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "3a4d09c7aa6d",
  "video_id": "charades_WI6NB",
  "format": "sp",
  "question": "Before wooden cabinets comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "wooden cabinets left the frame before coming back",
  "statement_B": "wooden cabinets was fully blocked before coming back"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="wooden cabinets"  video_length=44.6s  tracker_fps=5
Track 29 (mean_conf=0.35)
  visible: 4.0-30.8s
  first_seen: 4.0s at (0.06, 0.14)   last_seen: 30.8s at (0.01, 0.23)
  gaps: none
Track 25 (mean_conf=0.27)
  visible: 4.0-17.4s | 18.2-32.4s
  first_seen: 4.0s at (0.50, 0.50)   last_seen: 32.4s at (0.50, 0.50)
  gaps: 17.4-18.2s (last pos (0.50, 0.50))
Track 36 (mean_conf=0.28)
  visible: 6.8-6.8s | 8.4-26.6s | 27.8-28.0s | 28.6-29.2s | 29.8-30.2s | 30.8-30.8s
  first_seen: 6.8s at (0.50, 0.19)   last_seen: 30.8s at (0.50, 0.22)
  gaps: 6.8-8.4s (last pos (0.50, 0.19)) | 26.6-27.8s (last pos (0.50, 0.19)) | 28.0-28.6s (last pos (0.50, 0.20)) | 29.2-29.8s (last pos (0.50, 0.20)) | 30.2-30.8s (last pos (0.50, 0.21))
Track 51 (mean_conf=0.41)
  visible: 32.0-41.6s
  first_seen: 32.0s at (0.93, 0.19)   last_seen: 41.6s at (0.99, 0.21)
  gaps: none
Track 37 (mean_conf=0.22)
  visible: 5.4-6.0s | 6.6-10.8s | 13.6-18.6s | 19.2-19.2s | 21.2-23.4s | 24.8-26.4s | 28.8-28.8s | 30.6-30.6s
  first_seen: 5.4s at (0.50, 0.08)   last_seen: 30.6s at (0.38, 0.20)
  gaps: 6.0-6.6s (last pos (0.51, 0.11)) | 10.8-13.6s (last pos (0.44, 0.15)) | 18.6-19.2s (last pos (0.42, 0.16)) | 19.2-21.2s (last pos (0.41, 0.18)) | 23.4-24.8s (last pos (0.37, 0.20)) | 26.4-28.8s (last pos (0.40, 0.18)) | 28.8-30.6s (last pos (0.38, 0.20))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 36 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_correct_A_wrong / 46d5db724a2d

范围：test；可表达：True；视频：charades_G6LYD。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "46d5db724a2d",
  "video_id": "charades_G6LYD",
  "format": "sp",
  "question": "Before wall outlet comes back into view, was it fully blocked or did it left the frame?",
  "statement_A": "wall outlet left the frame before coming back",
  "statement_B": "wall outlet was fully blocked before coming back"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="wall outlet"  video_length=30.8s  tracker_fps=5
Track 44 (mean_conf=0.51)
  visible: 14.8-14.8s | 16.0-30.6s
  first_seen: 14.8s at (0.23, 0.01)   last_seen: 30.6s at (0.24, 0.27)
  gaps: 14.8-16.0s (last pos (0.23, 0.01))
Track 25 (mean_conf=0.29)
  visible: 9.6-11.0s | 13.0-14.0s | 14.8-14.8s | 15.6-17.0s | 18.2-18.2s | 18.8-24.0s | 24.6-26.2s | 27.2-30.6s
  first_seen: 9.6s at (0.36, 0.33)   last_seen: 30.6s at (0.35, 0.30)
  gaps: 11.0-13.0s (last pos (0.42, 0.38)) | 14.0-14.8s (last pos (0.33, 0.22)) | 14.8-15.6s (last pos (0.36, 0.02)) | 17.0-18.2s (last pos (0.34, 0.26)) | 18.2-18.8s (last pos (0.28, 0.15)) | 24.0-24.6s (last pos (0.37, 0.24)) | 26.2-27.2s (last pos (0.37, 0.23))
Track 0 (mean_conf=0.49)
  visible: 0.0-8.4s
  first_seen: 0.0s at (0.41, 0.44)   last_seen: 8.4s at (0.38, 0.37)
  gaps: none
Track 17 (mean_conf=0.50)
  visible: 8.8-14.2s
  first_seen: 8.8s at (0.36, 0.39)   last_seen: 14.2s at (0.20, 0.14)
  gaps: none
Track 1 (mean_conf=0.27)
  visible: 0.0-2.0s | 2.6-9.0s
  first_seen: 0.0s at (0.52, 0.47)   last_seen: 9.0s at (0.48, 0.41)
  gaps: 2.0-2.6s (last pos (0.53, 0.43))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 22 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_correct_A_wrong / 8e2cb6cbf96b

范围：test；可表达：True；视频：charades_KZTDH。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "8e2cb6cbf96b",
  "video_id": "charades_KZTDH",
  "format": "sp",
  "question": "Before wooden cabinet comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "wooden cabinet was fully blocked before coming back",
  "statement_B": "wooden cabinet left the frame before coming back"
}
```

真值：`B`。A解析：`A`；B解析：`B`。

A 原始输出：

```text
A
```

B 原始输出：

```text
B
```

完整轨迹文本：

```text
[Tracking results] query="wooden cabinet"  video_length=26.2s  tracker_fps=5
Track 0 (mean_conf=0.50)
  visible: 0.0-23.8s | 25.0-26.0s
  first_seen: 0.0s at (0.54, 0.27)   last_seen: 26.0s at (0.54, 0.27)
  gaps: 23.8-25.0s (last pos (0.54, 0.27))
Track 2 (mean_conf=0.33)
  visible: 1.4-1.6s | 2.2-10.4s
  first_seen: 1.4s at (0.50, 0.50)   last_seen: 10.4s at (0.50, 0.50)
  gaps: 1.6-2.2s (last pos (0.50, 0.50))
Track 1 (mean_conf=0.22)
  visible: 0.4-2.8s | 3.6-7.2s | 7.8-9.0s | 10.2-13.6s | 15.4-17.2s | 17.8-18.0s
  first_seen: 0.4s at (0.54, 0.91)   last_seen: 18.0s at (0.54, 0.90)
  gaps: 2.8-3.6s (last pos (0.54, 0.91)) | 7.2-7.8s (last pos (0.55, 0.90)) | 9.0-10.2s (last pos (0.55, 0.90)) | 13.6-15.4s (last pos (0.54, 0.91)) | 17.2-17.8s (last pos (0.54, 0.90))
Track 25 (mean_conf=0.37)
  visible: 25.0-26.0s
  first_seen: 25.0s at (0.55, 0.50)   last_seen: 26.0s at (0.53, 0.50)
  gaps: none
Track 4 (mean_conf=0.28)
  visible: 21.2-22.2s | 24.6-24.6s
  first_seen: 21.2s at (0.50, 0.50)   last_seen: 24.6s at (0.02, 0.60)
  gaps: 22.2-24.6s (last pos (0.50, 0.50))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 11 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_wrong_A_correct / 061682ce31ac

范围：test；可表达：True；视频：perception_test_video_6366。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "061682ce31ac",
  "video_id": "perception_test_video_6366",
  "format": "sp",
  "question": "Before white mug comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "white mug was fully blocked before coming back",
  "statement_B": "white mug left the frame before coming back"
}
```

真值：`A`。A解析：`A`；B解析：`B`。

A 原始输出：

```text
A
```

B 原始输出：

```text
B
```

完整轨迹文本：

```text
[Tracking results] query="white mug"  video_length=20.4s  tracker_fps=5
Track 4 (mean_conf=0.47)
  visible: 5.6-20.2s
  first_seen: 5.6s at (0.19, 0.56)   last_seen: 20.2s at (0.21, 0.56)
  gaps: none
Track 0 (mean_conf=0.82)
  visible: 0.0-5.4s
  first_seen: 0.0s at (0.75, 0.28)   last_seen: 5.4s at (0.76, 0.24)
  gaps: none
Track 2 (mean_conf=0.35)
  visible: 6.0-6.0s | 6.6-7.2s | 8.2-8.2s | 9.2-9.2s | 10.2-11.4s | 14.0-14.2s | 14.8-15.2s | 16.0-17.4s | 18.0-18.0s | 20.0-20.0s
  first_seen: 6.0s at (0.82, 0.62)   last_seen: 20.0s at (0.83, 0.63)
  gaps: 6.0-6.6s (last pos (0.82, 0.62)) | 7.2-8.2s (last pos (0.82, 0.62)) | 8.2-9.2s (last pos (0.82, 0.62)) | 9.2-10.2s (last pos (0.82, 0.62)) | 11.4-14.0s (last pos (0.82, 0.64)) | 14.2-14.8s (last pos (0.81, 0.62)) | 15.2-16.0s (last pos (0.81, 0.62)) | 17.4-18.0s (last pos (0.81, 0.62)) | 18.0-20.0s (last pos (0.81, 0.62))
Track 6 (mean_conf=0.38)
  visible: 5.6-6.4s | 9.0-9.0s | 11.8-12.2s | 13.8-13.8s | 14.6-14.6s | 15.8-15.8s | 17.6-17.8s | 18.6-18.8s | 19.4-19.8s
  first_seen: 5.6s at (0.82, 0.62)   last_seen: 19.8s at (0.81, 0.62)
  gaps: 6.4-9.0s (last pos (0.82, 0.62)) | 9.0-11.8s (last pos (0.82, 0.62)) | 12.2-13.8s (last pos (0.82, 0.64)) | 13.8-14.6s (last pos (0.81, 0.62)) | 14.6-15.8s (last pos (0.81, 0.62)) | 15.8-17.6s (last pos (0.81, 0.62)) | 17.8-18.6s (last pos (0.81, 0.62)) | 18.8-19.4s (last pos (0.81, 0.62))
Track 34 (mean_conf=0.33)
  visible: 14.4-14.4s | 15.0-15.6s | 17.0-17.0s | 18.2-18.4s | 19.0-19.2s | 20.2-20.2s
  first_seen: 14.4s at (0.81, 0.62)   last_seen: 20.2s at (0.83, 0.63)
  gaps: 14.4-15.0s (last pos (0.81, 0.62)) | 15.6-17.0s (last pos (0.81, 0.62)) | 17.0-18.2s (last pos (0.81, 0.62)) | 18.4-19.0s (last pos (0.81, 0.62)) | 19.2-20.2s (last pos (0.81, 0.62))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 4 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_wrong_A_correct / 09ecc5ba1b9b

范围：test；可表达：True；视频：perception_test_video_8872。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "09ecc5ba1b9b",
  "video_id": "perception_test_video_8872",
  "format": "sp",
  "question": "Before black leather couch comes back into view, was it fully blocked or did it left the frame?",
  "statement_A": "black leather couch left the frame before coming back",
  "statement_B": "black leather couch was fully blocked before coming back"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="black leather couch"  video_length=33.8s  tracker_fps=5
Track 36 (mean_conf=0.38)
  visible: 4.8-4.8s | 6.4-6.8s | 7.4-10.0s | 10.8-11.2s | 11.8-13.8s | 14.4-14.4s | 15.0-15.0s | 16.4-29.2s | 29.8-29.8s | 31.0-33.6s
  first_seen: 4.8s at (0.34, 0.36)   last_seen: 33.6s at (0.34, 0.41)
  gaps: 4.8-6.4s (last pos (0.34, 0.36)) | 6.8-7.4s (last pos (0.34, 0.39)) | 10.0-10.8s (last pos (0.34, 0.42)) | 11.2-11.8s (last pos (0.34, 0.49)) | 13.8-14.4s (last pos (0.35, 0.43)) | 14.4-15.0s (last pos (0.35, 0.38)) | 15.0-16.4s (last pos (0.34, 0.37)) | 29.2-29.8s (last pos (0.34, 0.38)) | 29.8-31.0s (last pos (0.36, 0.37))
Track 21 (mean_conf=0.29)
  visible: 3.0-5.0s | 6.0-6.0s | 8.2-8.2s | 16.2-16.4s | 17.4-17.4s | 22.2-30.2s | 30.8-32.6s
  first_seen: 3.0s at (0.36, 0.50)   last_seen: 32.6s at (0.33, 0.49)
  gaps: 5.0-6.0s (last pos (0.38, 0.50)) | 6.0-8.2s (last pos (0.37, 0.50)) | 8.2-16.2s (last pos (0.35, 0.50)) | 16.4-17.4s (last pos (0.35, 0.50)) | 17.4-22.2s (last pos (0.36, 0.50)) | 30.2-30.8s (last pos (0.36, 0.50))
Track 16 (mean_conf=0.34)
  visible: 3.8-4.0s | 11.0-11.6s | 13.2-22.0s | 24.0-24.0s
  first_seen: 3.8s at (0.42, 0.50)   last_seen: 24.0s at (0.34, 0.50)
  gaps: 4.0-11.0s (last pos (0.40, 0.50)) | 11.6-13.2s (last pos (0.35, 0.50)) | 22.0-24.0s (last pos (0.34, 0.52))
Track 32 (mean_conf=0.37)
  visible: 4.2-5.2s | 5.8-5.8s | 6.4-6.8s | 7.4-8.8s | 9.6-13.0s | 15.4-15.4s
  first_seen: 4.2s at (0.34, 0.56)   last_seen: 15.4s at (0.35, 0.56)
  gaps: 5.2-5.8s (last pos (0.35, 0.56)) | 5.8-6.4s (last pos (0.34, 0.55)) | 6.8-7.4s (last pos (0.34, 0.54)) | 8.8-9.6s (last pos (0.35, 0.52)) | 13.0-15.4s (last pos (0.35, 0.52))
Track 6 (mean_conf=0.33)
  visible: 2.0-2.4s | 4.2-4.2s | 5.4-6.2s | 7.0-7.2s | 7.8-7.8s | 8.6-9.4s | 10.2-10.2s | 16.4-16.4s | 17.4-17.4s | 18.2-18.8s | 22.6-23.0s
  first_seen: 2.0s at (0.36, 0.50)   last_seen: 23.0s at (0.34, 0.37)
  gaps: 2.4-4.2s (last pos (0.35, 0.50)) | 4.2-5.4s (last pos (0.34, 0.50)) | 6.2-7.0s (last pos (0.35, 0.56)) | 7.2-7.8s (last pos (0.35, 0.55)) | 7.8-8.6s (last pos (0.35, 0.55)) | 9.4-10.2s (last pos (0.35, 0.52)) | 10.2-16.4s (last pos (0.35, 0.55)) | 16.4-17.4s (last pos (0.35, 0.49)) | 17.4-18.2s (last pos (0.35, 0.47)) | 18.8-22.6s (last pos (0.34, 0.47))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 35 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_wrong_A_correct / 1299999226de

范围：test；可表达：True；视频：perception_test_video_6013。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "1299999226de",
  "video_id": "perception_test_video_6013",
  "format": "sp",
  "question": "Before tomato slices comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "tomato slices was fully blocked before coming back",
  "statement_B": "tomato slices left the frame before coming back"
}
```

真值：`A`。A解析：`A`；B解析：`B`。

A 原始输出：

```text
A
```

B 原始输出：

```text
B
```

完整轨迹文本：

```text
[Tracking results] query="tomato slices"  video_length=34.2s  tracker_fps=5
Track 0 (mean_conf=0.42)
  visible: 0.0-28.2s | 28.8-28.8s | 29.4-29.4s
  first_seen: 0.0s at (0.28, 0.44)   last_seen: 29.4s at (0.27, 0.43)
  gaps: 28.2-28.8s (last pos (0.27, 0.47)) | 28.8-29.4s (last pos (0.26, 0.42))
Track 30 (mean_conf=0.43)
  visible: 10.6-27.6s
  first_seen: 10.6s at (0.58, 0.34)   last_seen: 27.6s at (0.58, 0.35)
  gaps: none
Track 1 (mean_conf=0.40)
  visible: 0.0-7.0s
  first_seen: 0.0s at (0.58, 0.34)   last_seen: 7.0s at (0.58, 0.35)
  gaps: none
Track 17 (mean_conf=0.42)
  visible: 8.4-8.4s | 10.6-10.6s | 27.8-29.4s | 30.4-34.0s
  first_seen: 8.4s at (0.57, 0.31)   last_seen: 34.0s at (0.58, 0.35)
  gaps: 8.4-10.6s (last pos (0.57, 0.31)) | 10.6-27.8s (last pos (0.57, 0.31)) | 29.4-30.4s (last pos (0.58, 0.34))
Track 36 (mean_conf=0.32)
  visible: 29.6-34.0s
  first_seen: 29.6s at (0.33, 0.16)   last_seen: 34.0s at (0.42, 0.20)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 8 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_wrong_A_correct / 24773ab677ad

范围：test；可表达：True；视频：charades_Y4IIO。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "24773ab677ad",
  "video_id": "charades_Y4IIO",
  "format": "sp",
  "question": "Before microwave comes back into view, was it fully blocked or did it left the frame?",
  "statement_A": "microwave left the frame before coming back",
  "statement_B": "microwave was fully blocked before coming back"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="microwave"  video_length=34.0s  tracker_fps=5
Track 9 (mean_conf=0.41)
  visible: 14.6-19.0s | 20.8-29.6s
  first_seen: 14.6s at (0.55, 0.73)   last_seen: 29.6s at (0.51, 0.72)
  gaps: 19.0-20.8s (last pos (0.59, 0.73))
Track 25 (mean_conf=0.54)
  visible: 8.4-9.6s | 13.2-19.2s
  first_seen: 8.4s at (0.94, 0.75)   last_seen: 19.2s at (0.88, 0.75)
  gaps: 9.6-13.2s (last pos (0.89, 0.73))
Track 0 (mean_conf=0.52)
  visible: 0.0-1.2s | 3.6-3.8s | 7.6-7.8s | 10.0-10.2s | 30.2-33.8s
  first_seen: 0.0s at (0.88, 0.75)   last_seen: 33.8s at (0.88, 0.75)
  gaps: 1.2-3.6s (last pos (0.88, 0.71)) | 3.8-7.6s (last pos (0.93, 0.75)) | 7.8-10.0s (last pos (0.96, 0.71)) | 10.2-30.2s (last pos (0.96, 0.72))
Track 21 (mean_conf=0.43)
  visible: 4.4-7.0s | 11.8-12.6s
  first_seen: 4.4s at (0.49, 0.72)   last_seen: 12.6s at (0.48, 0.72)
  gaps: 7.0-11.8s (last pos (0.49, 0.72))
Track 29 (mean_conf=0.25)
  visible: 11.4-12.0s | 20.2-20.2s | 21.8-21.8s | 22.4-24.4s | 25.0-25.4s | 26.0-26.2s | 27.2-28.4s
  first_seen: 11.4s at (0.76, 0.21)   last_seen: 28.4s at (0.73, 0.21)
  gaps: 12.0-20.2s (last pos (0.77, 0.22)) | 20.2-21.8s (last pos (0.76, 0.21)) | 21.8-22.4s (last pos (0.82, 0.24)) | 24.4-25.0s (last pos (0.83, 0.26)) | 25.4-26.0s (last pos (0.82, 0.27)) | 26.2-27.2s (last pos (0.82, 0.25))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 17 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## R/D / B_wrong_A_correct / 298c2a249578

范围：test；可表达：True；视频：charades_KO34N。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "298c2a249578",
  "video_id": "charades_KO34N",
  "format": "sp",
  "question": "Before blue cloth comes back into view, was it fully blocked or did it leave the frame?",
  "statement_A": "blue cloth left the frame before coming back",
  "statement_B": "blue cloth was fully blocked before coming back"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="blue cloth"  video_length=30.8s  tracker_fps=5
Track 8 (mean_conf=0.45)
  visible: 11.6-30.6s
  first_seen: 11.6s at (0.40, 0.50)   last_seen: 30.6s at (0.19, 0.54)
  gaps: none
Track 1 (mean_conf=0.32)
  visible: 0.0-2.0s | 2.6-11.2s | 22.6-30.6s
  first_seen: 0.0s at (0.58, 0.87)   last_seen: 30.6s at (0.66, 0.92)
  gaps: 2.0-2.6s (last pos (0.59, 0.92)) | 11.2-22.6s (last pos (0.61, 0.92))
Track 0 (mean_conf=0.49)
  visible: 0.0-11.4s
  first_seen: 0.0s at (0.35, 0.50)   last_seen: 11.4s at (0.36, 0.50)
  gaps: none
Track 18 (mean_conf=0.28)
  visible: 19.4-23.0s | 23.6-24.6s | 25.6-26.2s | 26.8-26.8s | 28.2-28.2s | 30.6-30.6s
  first_seen: 19.4s at (0.33, 0.85)   last_seen: 30.6s at (0.41, 0.80)
  gaps: 23.0-23.6s (last pos (0.36, 0.77)) | 24.6-25.6s (last pos (0.37, 0.78)) | 26.2-26.8s (last pos (0.35, 0.76)) | 26.8-28.2s (last pos (0.36, 0.76)) | 28.2-30.6s (last pos (0.38, 0.73))
Track 15 (mean_conf=0.26)
  visible: 16.6-18.0s | 19.2-20.0s
  first_seen: 16.6s at (0.37, 0.83)   last_seen: 20.0s at (0.32, 0.94)
  gaps: 18.0-19.2s (last pos (0.32, 0.88))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 7 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_correct_A_wrong / 120825200c3f

范围：test；可表达：False；视频：charades_DHVYY。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "120825200c3f",
  "video_id": "charades_DHVYY",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "beige shirt gets partly hidden before black pants leaves the frame",
  "statement_B": "black pants leaves the frame before beige shirt gets partly hidden"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="beige shirt"  video_length=28.2s  tracker_fps=5
Track 0 (mean_conf=0.67)
  visible: 0.0-16.8s | 26.0-28.0s
  first_seen: 0.0s at (0.75, 0.53)   last_seen: 28.0s at (0.78, 0.51)
  gaps: 16.8-26.0s (last pos (0.87, 0.56))
Track 1 (mean_conf=0.34)
  visible: 17.2-26.0s
  first_seen: 17.2s at (0.33, 0.77)   last_seen: 26.0s at (0.33, 0.77)
  gaps: none
Track 6 (mean_conf=0.29)
  visible: 17.2-25.8s
  first_seen: 17.2s at (0.08, 0.90)   last_seen: 25.8s at (0.08, 0.90)
  gaps: none
Track 5 (mean_conf=0.26)
  visible: 17.0-25.6s
  first_seen: 17.0s at (0.81, 0.78)   last_seen: 25.6s at (0.84, 0.87)
  gaps: none
Track 7 (mean_conf=0.25)
  visible: 17.4-24.8s | 25.6-25.8s
  first_seen: 17.4s at (0.28, 0.77)   last_seen: 25.8s at (0.28, 0.78)
  gaps: 24.8-25.6s (last pos (0.29, 0.77))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 3 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="black pants"  video_length=28.2s  tracker_fps=5
Track 3 (mean_conf=0.35)
  visible: 6.0-6.2s | 7.2-8.0s | 9.6-9.6s | 10.2-10.2s | 11.2-11.2s | 12.4-12.4s | 17.8-24.6s
  first_seen: 6.0s at (0.76, 0.78)   last_seen: 24.6s at (0.66, 0.91)
  gaps: 6.2-7.2s (last pos (0.76, 0.78)) | 8.0-9.6s (last pos (0.75, 0.77)) | 9.6-10.2s (last pos (0.75, 0.77)) | 10.2-11.2s (last pos (0.75, 0.75)) | 11.2-12.4s (last pos (0.75, 0.75)) | 12.4-17.8s (last pos (0.74, 0.75))
Track 9 (mean_conf=0.31)
  visible: 17.6-26.0s
  first_seen: 17.6s at (0.59, 0.74)   last_seen: 26.0s at (0.59, 0.74)
  gaps: none
Track 10 (mean_conf=0.25)
  visible: 19.6-23.0s | 23.8-24.0s
  first_seen: 19.6s at (0.33, 0.77)   last_seen: 24.0s at (0.33, 0.77)
  gaps: 23.0-23.8s (last pos (0.33, 0.77))
Track 4 (mean_conf=0.43)
  visible: 16.4-16.6s | 26.6-28.0s
  first_seen: 16.4s at (0.86, 0.77)   last_seen: 28.0s at (0.80, 0.78)
  gaps: 16.6-26.6s (last pos (0.89, 0.75))
Track 0 (mean_conf=0.55)
  visible: 13.4-13.8s | 16.4-16.4s | 17.0-17.6s
  first_seen: 13.4s at (0.72, 0.63)   last_seen: 17.6s at (0.96, 0.60)
  gaps: 13.8-16.4s (last pos (0.72, 0.68)) | 16.4-17.0s (last pos (0.84, 0.55))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 4 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_correct_A_wrong / 16f94195d2e3

范围：test；可表达：False；视频：perception_test_video_6366。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "16f94195d2e3",
  "video_id": "perception_test_video_6366",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "white mug gets fully hidden before lettuce leaf gets partly hidden",
  "statement_B": "lettuce leaf gets partly hidden before white mug gets fully hidden"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="white mug"  video_length=20.4s  tracker_fps=5
Track 4 (mean_conf=0.47)
  visible: 5.6-20.2s
  first_seen: 5.6s at (0.19, 0.56)   last_seen: 20.2s at (0.21, 0.56)
  gaps: none
Track 0 (mean_conf=0.82)
  visible: 0.0-5.4s
  first_seen: 0.0s at (0.75, 0.28)   last_seen: 5.4s at (0.76, 0.24)
  gaps: none
Track 2 (mean_conf=0.35)
  visible: 6.0-6.0s | 6.6-7.2s | 8.2-8.2s | 9.2-9.2s | 10.2-11.4s | 14.0-14.2s | 14.8-15.2s | 16.0-17.4s | 18.0-18.0s | 20.0-20.0s
  first_seen: 6.0s at (0.82, 0.62)   last_seen: 20.0s at (0.83, 0.63)
  gaps: 6.0-6.6s (last pos (0.82, 0.62)) | 7.2-8.2s (last pos (0.82, 0.62)) | 8.2-9.2s (last pos (0.82, 0.62)) | 9.2-10.2s (last pos (0.82, 0.62)) | 11.4-14.0s (last pos (0.82, 0.64)) | 14.2-14.8s (last pos (0.81, 0.62)) | 15.2-16.0s (last pos (0.81, 0.62)) | 17.4-18.0s (last pos (0.81, 0.62)) | 18.0-20.0s (last pos (0.81, 0.62))
Track 6 (mean_conf=0.38)
  visible: 5.6-6.4s | 9.0-9.0s | 11.8-12.2s | 13.8-13.8s | 14.6-14.6s | 15.8-15.8s | 17.6-17.8s | 18.6-18.8s | 19.4-19.8s
  first_seen: 5.6s at (0.82, 0.62)   last_seen: 19.8s at (0.81, 0.62)
  gaps: 6.4-9.0s (last pos (0.82, 0.62)) | 9.0-11.8s (last pos (0.82, 0.62)) | 12.2-13.8s (last pos (0.82, 0.64)) | 13.8-14.6s (last pos (0.81, 0.62)) | 14.6-15.8s (last pos (0.81, 0.62)) | 15.8-17.6s (last pos (0.81, 0.62)) | 17.8-18.6s (last pos (0.81, 0.62)) | 18.8-19.4s (last pos (0.81, 0.62))
Track 34 (mean_conf=0.33)
  visible: 14.4-14.4s | 15.0-15.6s | 17.0-17.0s | 18.2-18.4s | 19.0-19.2s | 20.2-20.2s
  first_seen: 14.4s at (0.81, 0.62)   last_seen: 20.2s at (0.83, 0.63)
  gaps: 14.4-15.0s (last pos (0.81, 0.62)) | 15.6-17.0s (last pos (0.81, 0.62)) | 17.0-18.2s (last pos (0.81, 0.62)) | 18.4-19.0s (last pos (0.81, 0.62)) | 19.2-20.2s (last pos (0.81, 0.62))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 4 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="lettuce leaf"  video_length=20.4s  tracker_fps=5
Track 1 (mean_conf=0.73)
  visible: 0.0-8.0s
  first_seen: 0.0s at (0.90, 0.62)   last_seen: 8.0s at (0.91, 0.43)
  gaps: none
Track 3 (mean_conf=0.43)
  visible: 9.6-9.6s | 11.8-12.2s | 13.8-20.2s
  first_seen: 9.6s at (0.87, 0.59)   last_seen: 20.2s at (0.88, 0.62)
  gaps: 9.6-11.8s (last pos (0.87, 0.59)) | 12.2-13.8s (last pos (0.87, 0.62))
Track 35 (mean_conf=0.42)
  visible: 16.0-20.2s
  first_seen: 16.0s at (0.53, 0.53)   last_seen: 20.2s at (0.54, 0.56)
  gaps: none
Track 28 (mean_conf=0.41)
  visible: 12.0-15.8s
  first_seen: 12.0s at (0.57, 0.49)   last_seen: 15.8s at (0.53, 0.45)
  gaps: none
Track 22 (mean_conf=0.61)
  visible: 9.6-11.8s
  first_seen: 9.6s at (0.56, 0.42)   last_seen: 11.8s at (0.57, 0.42)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 12 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_correct_A_wrong / 1bc39a39d493

范围：test；可表达：True；视频：charades_3FEYY。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "1bc39a39d493",
  "video_id": "charades_3FEYY",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "red towel gets fully hidden before black pants leaves the frame",
  "statement_B": "black pants leaves the frame before red towel gets fully hidden"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="red towel"  video_length=30.0s  tracker_fps=5
Track 1 (mean_conf=0.37)
  visible: 0.0-16.0s | 18.2-18.6s | 19.4-20.2s | 20.8-21.4s | 26.0-29.8s
  first_seen: 0.0s at (0.16, 0.84)   last_seen: 29.8s at (0.16, 0.84)
  gaps: 16.0-18.2s (last pos (0.07, 0.85)) | 18.6-19.4s (last pos (0.23, 0.84)) | 20.2-20.8s (last pos (0.24, 0.81)) | 21.4-26.0s (last pos (0.22, 0.87))
Track 3 (mean_conf=0.35)
  visible: 15.6-15.6s | 17.0-18.0s | 18.8-19.0s | 21.6-29.8s
  first_seen: 15.6s at (0.14, 0.84)   last_seen: 29.8s at (0.17, 0.88)
  gaps: 15.6-17.0s (last pos (0.14, 0.84)) | 18.0-18.8s (last pos (0.16, 0.88)) | 19.0-21.6s (last pos (0.18, 0.88))
Track 0 (mean_conf=0.44)
  visible: 16.0-16.0s | 18.6-21.2s | 22.0-22.4s | 24.8-25.0s
  first_seen: 16.0s at (0.24, 0.59)   last_seen: 25.0s at (0.17, 0.62)
  gaps: 16.0-18.6s (last pos (0.24, 0.59)) | 21.2-22.0s (last pos (0.13, 0.61)) | 22.4-24.8s (last pos (0.15, 0.61))
Track 6 (mean_conf=0.27)
  visible: 16.2-16.8s
  first_seen: 16.2s at (0.94, 0.55)   last_seen: 16.8s at (0.94, 0.51)
  gaps: none
Track 15 (mean_conf=0.39)
  visible: 25.2-25.2s | 26.0-26.0s
  first_seen: 25.2s at (0.17, 0.62)   last_seen: 26.0s at (0.10, 0.59)
  gaps: 25.2-26.0s (last pos (0.17, 0.62))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 3 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="black pants"  video_length=30.0s  tracker_fps=5
Track 0 (mean_conf=0.69)
  visible: 0.0-18.4s | 21.4-24.6s | 25.2-25.2s
  first_seen: 0.0s at (0.54, 0.59)   last_seen: 25.2s at (0.17, 0.62)
  gaps: 18.4-21.4s (last pos (0.13, 0.60)) | 24.6-25.2s (last pos (0.13, 0.61))
Track 4 (mean_conf=0.30)
  visible: 10.6-11.6s | 12.2-24.0s | 24.6-26.2s
  first_seen: 10.6s at (0.52, 0.83)   last_seen: 26.2s at (0.03, 0.90)
  gaps: 11.6-12.2s (last pos (0.52, 0.83)) | 24.0-24.6s (last pos (0.08, 0.83))
Track 2 (mean_conf=0.21)
  visible: 0.0-0.0s | 1.0-4.0s | 4.6-9.6s
  first_seen: 0.0s at (0.51, 0.83)   last_seen: 9.6s at (0.52, 0.83)
  gaps: 0.0-1.0s (last pos (0.51, 0.83)) | 4.0-4.6s (last pos (0.51, 0.83))
Track 7 (mean_conf=0.30)
  visible: 26.4-29.8s
  first_seen: 26.4s at (0.86, 0.93)   last_seen: 29.8s at (0.86, 0.93)
  gaps: none
Track 15 (mean_conf=0.41)
  visible: 25.0-26.4s
  first_seen: 25.0s at (0.17, 0.62)   last_seen: 26.4s at (0.04, 0.67)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_correct_A_wrong / 1e127320a187

范围：test；可表达：False；视频：charades_XZLNT。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "1e127320a187",
  "video_id": "charades_XZLNT",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "wooden shelf gets partly hidden before woman with curly hair leaves the frame",
  "statement_B": "woman with curly hair leaves the frame before wooden shelf gets partly hidden"
}
```

真值：`A`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="wooden shelf"  video_length=30.0s  tracker_fps=5
Track 0 (mean_conf=0.45)
  visible: 0.0-29.8s
  first_seen: 0.0s at (0.48, 0.43)   last_seen: 29.8s at (0.48, 0.42)
  gaps: none
Track 1 (mean_conf=0.25)
  visible: 8.4-9.8s | 10.4-10.6s | 12.8-16.4s | 17.0-18.0s | 20.0-20.2s | 21.6-21.8s | 23.4-23.4s | 24.8-27.0s
  first_seen: 8.4s at (0.19, 0.38)   last_seen: 27.0s at (0.19, 0.38)
  gaps: 9.8-10.4s (last pos (0.19, 0.38)) | 10.6-12.8s (last pos (0.19, 0.38)) | 16.4-17.0s (last pos (0.19, 0.38)) | 18.0-20.0s (last pos (0.19, 0.38)) | 20.2-21.6s (last pos (0.19, 0.38)) | 21.8-23.4s (last pos (0.19, 0.38)) | 23.4-24.8s (last pos (0.19, 0.38))
Track 11 (mean_conf=0.30)
  visible: 26.4-26.4s
  first_seen: 26.4s at (0.45, 0.16)   last_seen: 26.4s at (0.45, 0.16)
  gaps: none
Track 4 (mean_conf=0.30)
  visible: 27.0-27.0s
  first_seen: 27.0s at (0.35, 0.42)   last_seen: 27.0s at (0.35, 0.42)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.

[Tracking results] query="woman with curly hair" : no retained detections after the registered filter.
Note: 2 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_correct_A_wrong / 324a59b08b0f

范围：test；可表达：False；视频：charades_1GQ73。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "324a59b08b0f",
  "video_id": "charades_1GQ73",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "man in grey hoodie gets partly hidden before wooden door frame enters the frame",
  "statement_B": "wooden door frame enters the frame before man in grey hoodie gets partly hidden"
}
```

真值：`B`。A解析：`A`；B解析：`B`。

A 原始输出：

```text
A
```

B 原始输出：

```text
B
```

完整轨迹文本：

```text
[Tracking results] query="man in grey hoodie"  video_length=30.8s  tracker_fps=5
Track 24 (mean_conf=0.22)
  visible: 12.8-19.8s | 20.6-23.6s | 24.2-26.0s
  first_seen: 12.8s at (0.57, 0.62)   last_seen: 26.0s at (0.59, 0.52)
  gaps: 19.8-20.6s (last pos (0.60, 0.62)) | 23.6-24.2s (last pos (0.49, 0.56))
Track 3 (mean_conf=0.23)
  visible: 0.0-1.4s | 2.0-2.6s | 3.2-9.4s | 12.0-12.0s
  first_seen: 0.0s at (0.47, 0.66)   last_seen: 12.0s at (0.45, 0.57)
  gaps: 1.4-2.0s (last pos (0.45, 0.66)) | 2.6-3.2s (last pos (0.41, 0.66)) | 9.4-12.0s (last pos (0.54, 0.64))
Track 31 (mean_conf=0.23)
  visible: 27.8-27.8s | 28.4-28.6s
  first_seen: 27.8s at (0.52, 0.59)   last_seen: 28.6s at (0.55, 0.58)
  gaps: 27.8-28.4s (last pos (0.52, 0.59))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="wooden door frame"  video_length=30.8s  tracker_fps=5
Track 5 (mean_conf=0.26)
  visible: 0.2-10.4s | 11.0-12.6s | 15.2-16.0s | 16.8-19.2s | 19.8-19.8s | 22.4-25.0s | 27.8-28.8s | 29.6-29.6s | 30.2-30.6s
  first_seen: 0.2s at (0.48, 0.50)   last_seen: 30.6s at (0.46, 0.50)
  gaps: 10.4-11.0s (last pos (0.49, 0.50)) | 12.6-15.2s (last pos (0.48, 0.50)) | 16.0-16.8s (last pos (0.48, 0.50)) | 19.2-19.8s (last pos (0.47, 0.50)) | 19.8-22.4s (last pos (0.48, 0.50)) | 25.0-27.8s (last pos (0.48, 0.50)) | 28.8-29.6s (last pos (0.48, 0.50)) | 29.6-30.2s (last pos (0.48, 0.50))
Track 6 (mean_conf=0.29)
  visible: 1.6-2.0s | 2.6-6.4s | 7.2-7.2s | 8.0-8.6s | 10.0-21.6s | 24.6-24.8s
  first_seen: 1.6s at (0.68, 0.50)   last_seen: 24.8s at (0.31, 0.50)
  gaps: 2.0-2.6s (last pos (0.68, 0.50)) | 6.4-7.2s (last pos (0.69, 0.50)) | 7.2-8.0s (last pos (0.68, 0.50)) | 8.6-10.0s (last pos (0.68, 0.50)) | 21.6-24.6s (last pos (0.31, 0.50))
Track 2 (mean_conf=0.32)
  visible: 0.0-10.0s
  first_seen: 0.0s at (0.30, 0.50)   last_seen: 10.0s at (0.32, 0.50)
  gaps: none
Track 1 (mean_conf=0.32)
  visible: 1.8-2.2s | 2.8-3.0s | 4.6-4.6s | 5.2-5.6s | 7.8-7.8s | 13.6-13.6s | 15.6-16.8s | 18.8-18.8s | 20.8-22.6s | 24.2-24.2s | 24.8-25.2s | 27.0-27.0s | 30.0-30.6s
  first_seen: 1.8s at (0.38, 0.58)   last_seen: 30.6s at (0.36, 0.51)
  gaps: 2.2-2.8s (last pos (0.38, 0.57)) | 3.0-4.6s (last pos (0.38, 0.58)) | 4.6-5.2s (last pos (0.40, 0.57)) | 5.6-7.8s (last pos (0.39, 0.58)) | 7.8-13.6s (last pos (0.39, 0.56)) | 13.6-15.6s (last pos (0.38, 0.54)) | 16.8-18.8s (last pos (0.36, 0.52)) | 18.8-20.8s (last pos (0.37, 0.52)) | 22.6-24.2s (last pos (0.39, 0.50)) | 24.2-24.8s (last pos (0.38, 0.51)) | 25.2-27.0s (last pos (0.38, 0.51)) | 27.0-30.0s (last pos (0.38, 0.52))
Track 19 (mean_conf=0.24)
  visible: 11.2-12.0s | 12.8-13.6s | 14.2-14.4s | 16.0-16.0s | 16.8-17.6s | 18.4-18.4s | 19.6-19.8s | 25.2-25.4s | 27.0-30.4s
  first_seen: 11.2s at (0.68, 0.50)   last_seen: 30.4s at (0.29, 0.50)
  gaps: 12.0-12.8s (last pos (0.67, 0.50)) | 13.6-14.2s (last pos (0.67, 0.50)) | 14.4-16.0s (last pos (0.67, 0.50)) | 16.0-16.8s (last pos (0.67, 0.50)) | 17.6-18.4s (last pos (0.68, 0.50)) | 18.4-19.6s (last pos (0.67, 0.50)) | 19.8-25.2s (last pos (0.69, 0.50)) | 25.4-27.0s (last pos (0.31, 0.50))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 15 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_wrong_A_correct / 12c70baa67ab

范围：test；可表达：False；视频：charades_X9ULK。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "12c70baa67ab",
  "video_id": "charades_X9ULK",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "white sink leaves the frame before mirror gets partly hidden",
  "statement_B": "mirror gets partly hidden before white sink leaves the frame"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="white sink"  video_length=30.4s  tracker_fps=5
Track 7 (mean_conf=0.46)
  visible: 1.6-1.6s | 2.2-7.8s | 8.6-17.2s
  first_seen: 1.6s at (0.75, 0.81)   last_seen: 17.2s at (0.59, 0.66)
  gaps: 1.6-2.2s (last pos (0.75, 0.81)) | 7.8-8.6s (last pos (0.81, 0.89))
Track 9 (mean_conf=0.32)
  visible: 4.4-4.4s | 7.0-7.0s | 8.0-8.2s | 12.8-12.8s | 16.2-20.8s | 22.0-22.4s
  first_seen: 4.4s at (0.73, 0.88)   last_seen: 22.4s at (0.74, 0.73)
  gaps: 4.4-7.0s (last pos (0.73, 0.88)) | 7.0-8.0s (last pos (0.79, 0.84)) | 8.2-12.8s (last pos (0.72, 0.84)) | 12.8-16.2s (last pos (0.73, 0.84)) | 20.8-22.0s (last pos (0.74, 0.72))
Track 0 (mean_conf=0.41)
  visible: 0.0-2.6s
  first_seen: 0.0s at (0.71, 0.93)   last_seen: 2.6s at (0.77, 0.79)
  gaps: none
Track 28 (mean_conf=0.46)
  visible: 20.8-22.6s
  first_seen: 20.8s at (0.92, 0.97)   last_seen: 22.6s at (0.92, 0.99)
  gaps: none
Track 30 (mean_conf=0.26)
  visible: 26.8-28.4s | 29.0-30.2s
  first_seen: 26.8s at (0.51, 0.93)   last_seen: 30.2s at (0.45, 0.98)
  gaps: 28.4-29.0s (last pos (0.46, 0.95))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 17 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="mirror"  video_length=30.4s  tracker_fps=5
Track 1 (mean_conf=0.55)
  visible: 0.0-24.2s | 24.8-25.8s
  first_seen: 0.0s at (0.91, 0.46)   last_seen: 25.8s at (0.91, 0.43)
  gaps: 24.2-24.8s (last pos (0.82, 0.43))
Track 38 (mean_conf=0.32)
  visible: 26.0-29.2s
  first_seen: 26.0s at (0.50, 0.50)   last_seen: 29.2s at (0.50, 0.50)
  gaps: none
Track 49 (mean_conf=0.25)
  visible: 26.6-29.8s
  first_seen: 26.6s at (0.66, 0.50)   last_seen: 29.8s at (0.64, 0.50)
  gaps: none
Track 5 (mean_conf=0.28)
  visible: 7.4-7.4s | 8.6-8.6s | 9.4-9.4s | 26.2-26.4s | 28.8-28.8s | 29.4-30.2s
  first_seen: 7.4s at (0.50, 0.50)   last_seen: 30.2s at (0.50, 0.50)
  gaps: 7.4-8.6s (last pos (0.50, 0.50)) | 8.6-9.4s (last pos (0.50, 0.50)) | 9.4-26.2s (last pos (0.50, 0.50)) | 26.4-28.8s (last pos (0.61, 0.50)) | 28.8-29.4s (last pos (0.50, 0.50))
Track 43 (mean_conf=0.24)
  visible: 26.2-26.2s | 27.0-27.0s | 27.6-28.6s | 30.0-30.2s
  first_seen: 26.2s at (0.69, 0.50)   last_seen: 30.2s at (0.67, 0.50)
  gaps: 26.2-27.0s (last pos (0.69, 0.50)) | 27.0-27.6s (last pos (0.76, 0.50)) | 28.6-30.0s (last pos (0.75, 0.50))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 12 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_wrong_A_correct / 15554ceb91bf

范围：test；可表达：False；视频：charades_06NUT。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "15554ceb91bf",
  "video_id": "charades_06NUT",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "tv stand gets fully hidden before black rug gets partly hidden",
  "statement_B": "black rug gets partly hidden before tv stand gets fully hidden"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="tv stand"  video_length=28.8s  tracker_fps=5
Track 13 (mean_conf=0.45)
  visible: 1.6-2.0s | 4.0-14.6s | 17.4-18.2s | 20.2-20.8s | 25.2-27.6s | 28.6-28.6s
  first_seen: 1.6s at (0.08, 0.90)   last_seen: 28.6s at (0.08, 0.44)
  gaps: 2.0-4.0s (last pos (0.07, 0.88)) | 14.6-17.4s (last pos (0.06, 0.56)) | 18.2-20.2s (last pos (0.04, 0.49)) | 20.8-25.2s (last pos (0.04, 0.48)) | 27.6-28.6s (last pos (0.09, 0.47))
Track 31 (mean_conf=0.38)
  visible: 15.0-17.2s | 18.6-19.8s | 21.2-24.2s | 25.8-26.6s | 27.8-28.4s
  first_seen: 15.0s at (0.88, 0.58)   last_seen: 28.4s at (0.96, 0.44)
  gaps: 17.2-18.6s (last pos (0.95, 0.52)) | 19.8-21.2s (last pos (0.96, 0.48)) | 24.2-25.8s (last pos (0.96, 0.45)) | 26.6-27.8s (last pos (0.96, 0.50))
Track 10 (mean_conf=0.29)
  visible: 1.0-1.4s | 6.4-6.4s | 11.6-11.6s | 14.8-14.8s | 17.2-17.8s | 18.4-26.6s | 27.2-27.2s | 27.8-28.4s
  first_seen: 1.0s at (0.80, 0.49)   last_seen: 28.4s at (0.82, 0.46)
  gaps: 1.4-6.4s (last pos (0.89, 0.45)) | 6.4-11.6s (last pos (0.97, 0.50)) | 11.6-14.8s (last pos (0.89, 0.59)) | 14.8-17.2s (last pos (0.75, 0.58)) | 17.8-18.4s (last pos (0.92, 0.53)) | 26.6-27.2s (last pos (0.82, 0.52)) | 27.2-27.8s (last pos (0.78, 0.54))
Track 1 (mean_conf=0.56)
  visible: 0.0-0.8s | 2.0-4.0s
  first_seen: 0.0s at (0.17, 0.51)   last_seen: 4.0s at (0.95, 0.49)
  gaps: 0.8-2.0s (last pos (0.15, 0.50))
Track 41 (mean_conf=0.23)
  visible: 18.2-18.6s | 20.4-20.4s | 28.2-28.6s
  first_seen: 18.2s at (0.26, 0.51)   last_seen: 28.6s at (0.35, 0.47)
  gaps: 18.6-20.4s (last pos (0.24, 0.46)) | 20.4-28.2s (last pos (0.27, 0.52))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 3 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="black rug"  video_length=28.8s  tracker_fps=5
Track 38 (mean_conf=0.28)
  visible: 10.8-10.8s | 18.0-18.8s | 19.4-21.4s | 22.6-28.4s
  first_seen: 10.8s at (0.01, 0.70)   last_seen: 28.4s at (0.88, 0.82)
  gaps: 10.8-18.0s (last pos (0.01, 0.70)) | 18.8-19.4s (last pos (0.84, 0.69)) | 21.4-22.6s (last pos (0.86, 0.76))
Track 7 (mean_conf=0.26)
  visible: 4.4-5.4s | 6.8-7.8s | 10.0-10.0s | 11.8-11.8s | 18.4-19.4s | 20.0-20.0s | 20.6-26.0s | 28.2-28.4s
  first_seen: 4.4s at (0.50, 0.77)   last_seen: 28.4s at (0.50, 0.76)
  gaps: 5.4-6.8s (last pos (0.50, 0.79)) | 7.8-10.0s (last pos (0.50, 0.78)) | 10.0-11.8s (last pos (0.50, 0.79)) | 11.8-18.4s (last pos (0.50, 0.81)) | 19.4-20.0s (last pos (0.50, 0.77)) | 20.0-20.6s (last pos (0.50, 0.78)) | 26.0-28.2s (last pos (0.50, 0.77))
Track 0 (mean_conf=0.49)
  visible: 0.0-0.6s | 1.6-4.0s
  first_seen: 0.0s at (0.32, 0.62)   last_seen: 4.0s at (0.96, 0.69)
  gaps: 0.6-1.6s (last pos (0.26, 0.63))
Track 52 (mean_conf=0.51)
  visible: 14.8-17.0s
  first_seen: 14.8s at (0.97, 0.82)   last_seen: 17.0s at (0.94, 0.76)
  gaps: none
Track 35 (mean_conf=0.29)
  visible: 8.8-9.4s | 12.8-13.4s | 14.0-14.0s
  first_seen: 8.8s at (0.05, 0.71)   last_seen: 14.0s at (0.06, 0.86)
  gaps: 9.4-12.8s (last pos (0.02, 0.67)) | 13.4-14.0s (last pos (0.06, 0.86))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 26 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_wrong_A_correct / 2175d655dec0

范围：test；可表达：True；视频：charades_2U903。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "2175d655dec0",
  "video_id": "charades_2U903",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "curtain leaves the frame before green dress on hanger leaves the frame",
  "statement_B": "green dress on hanger leaves the frame before curtain leaves the frame"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="curtain"  video_length=26.2s  tracker_fps=5
Track 37 (mean_conf=0.44)
  visible: 17.4-18.0s | 19.2-19.2s | 19.8-23.0s | 24.2-24.8s
  first_seen: 17.4s at (0.27, 0.21)   last_seen: 24.8s at (0.27, 0.38)
  gaps: 18.0-19.2s (last pos (0.24, 0.21)) | 19.2-19.8s (last pos (0.40, 0.25)) | 23.0-24.2s (last pos (0.33, 0.37))
Track 11 (mean_conf=0.34)
  visible: 3.6-4.4s | 8.6-8.8s | 9.4-12.4s
  first_seen: 3.6s at (0.16, 0.22)   last_seen: 12.4s at (0.04, 0.15)
  gaps: 4.4-8.6s (last pos (0.14, 0.18)) | 8.8-9.4s (last pos (0.05, 0.15))
Track 2 (mean_conf=0.31)
  visible: 0.0-1.0s | 1.6-5.0s | 7.4-7.4s
  first_seen: 0.0s at (0.49, 0.30)   last_seen: 7.4s at (0.35, 0.23)
  gaps: 1.0-1.6s (last pos (0.49, 0.30)) | 5.0-7.4s (last pos (0.57, 0.23))
Track 28 (mean_conf=0.41)
  visible: 14.0-17.0s
  first_seen: 14.0s at (0.10, 0.20)   last_seen: 17.0s at (0.31, 0.13)
  gaps: none
Track 0 (mean_conf=0.36)
  visible: 0.0-1.0s | 1.6-3.4s
  first_seen: 0.0s at (0.15, 0.22)   last_seen: 3.4s at (0.09, 0.21)
  gaps: 1.0-1.6s (last pos (0.16, 0.22))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 19 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="green dress on hanger"  video_length=26.2s  tracker_fps=5
Track 7 (mean_conf=0.27)
  visible: 17.4-18.4s | 19.0-26.0s
  first_seen: 17.4s at (0.69, 0.17)   last_seen: 26.0s at (0.56, 0.39)
  gaps: 18.4-19.0s (last pos (0.79, 0.17))
Track 19 (mean_conf=0.22)
  visible: 13.6-13.6s | 14.2-17.0s
  first_seen: 13.6s at (0.20, 0.66)   last_seen: 17.0s at (0.19, 0.56)
  gaps: 13.6-14.2s (last pos (0.20, 0.66))
Track 0 (mean_conf=0.29)
  visible: 3.6-5.4s
  first_seen: 3.6s at (0.09, 0.27)   last_seen: 5.4s at (0.10, 0.22)
  gaps: none
Track 1 (mean_conf=0.32)
  visible: 0.0-1.4s
  first_seen: 0.0s at (0.08, 0.28)   last_seen: 1.4s at (0.07, 0.27)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_wrong_A_correct / 35e1be5c9e71

范围：test；可表达：False；视频：perception_test_video_5234。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "35e1be5c9e71",
  "video_id": "perception_test_video_5234",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "knife gets fully hidden before potted plant gets partly hidden",
  "statement_B": "potted plant gets partly hidden before knife gets fully hidden"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="knife"  video_length=18.0s  tracker_fps=5
Track 18 (mean_conf=0.43)
  visible: 1.4-2.2s | 3.0-6.2s | 7.0-7.0s
  first_seen: 1.4s at (0.70, 0.53)   last_seen: 7.0s at (0.65, 0.51)
  gaps: 2.2-3.0s (last pos (0.67, 0.51)) | 6.2-7.0s (last pos (0.65, 0.51))
Track 38 (mean_conf=0.34)
  visible: 5.0-5.0s | 7.2-7.6s | 13.4-14.6s | 15.6-17.8s
  first_seen: 5.0s at (0.71, 0.53)   last_seen: 17.8s at (0.67, 0.51)
  gaps: 5.0-7.2s (last pos (0.71, 0.53)) | 7.6-13.4s (last pos (0.70, 0.53)) | 14.6-15.6s (last pos (0.67, 0.51))
Track 79 (mean_conf=0.24)
  visible: 15.6-17.0s | 17.8-17.8s
  first_seen: 15.6s at (0.51, 0.66)   last_seen: 17.8s at (0.52, 0.66)
  gaps: 17.0-17.8s (last pos (0.52, 0.66))
Track 1 (mean_conf=0.41)
  visible: 0.0-0.6s
  first_seen: 0.0s at (0.67, 0.51)   last_seen: 0.6s at (0.72, 0.53)
  gaps: none
Track 32 (mean_conf=0.31)
  visible: 16.8-16.8s
  first_seen: 16.8s at (0.68, 0.88)   last_seen: 16.8s at (0.68, 0.88)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 11 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="potted plant"  video_length=18.0s  tracker_fps=5
Track 69 (mean_conf=0.63)
  visible: 13.6-14.6s | 15.4-17.8s
  first_seen: 13.6s at (0.55, 0.40)   last_seen: 17.8s at (0.55, 0.47)
  gaps: 14.6-15.4s (last pos (0.55, 0.43))
Track 5 (mean_conf=0.65)
  visible: 0.4-0.6s | 4.0-6.2s | 7.0-7.2s
  first_seen: 0.4s at (0.55, 0.42)   last_seen: 7.2s at (0.56, 0.43)
  gaps: 0.6-4.0s (last pos (0.59, 0.39)) | 6.2-7.0s (last pos (0.55, 0.44))
Track 15 (mean_conf=0.64)
  visible: 1.0-2.6s
  first_seen: 1.0s at (0.53, 0.48)   last_seen: 2.6s at (0.54, 0.48)
  gaps: none
Track 26 (mean_conf=0.70)
  visible: 3.0-3.8s
  first_seen: 3.0s at (0.55, 0.43)   last_seen: 3.8s at (0.55, 0.47)
  gaps: none
Track 19 (mean_conf=0.32)
  visible: 1.4-2.2s | 3.2-3.2s
  first_seen: 1.4s at (0.64, 0.55)   last_seen: 3.2s at (0.64, 0.56)
  gaps: 2.2-3.2s (last pos (0.64, 0.56))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 7 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## X-Order / B_wrong_A_correct / 4c7a14e86d78

范围：test；可表达：False；视频：perception_test_video_3967。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "4c7a14e86d78",
  "video_id": "perception_test_video_3967",
  "format": "sp",
  "question": "Which event happens first in the video?",
  "statement_A": "pen gets partly hidden before power outlet gets partly hidden",
  "statement_B": "power outlet gets partly hidden before pen gets partly hidden"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A
```

完整轨迹文本：

```text
[Tracking results] query="pen"  video_length=25.0s  tracker_fps=5
Track 1 (mean_conf=0.42)
  visible: 0.0-18.2s
  first_seen: 0.0s at (0.41, 0.84)   last_seen: 18.2s at (0.41, 0.84)
  gaps: none
Track 53 (mean_conf=0.31)
  visible: 19.4-19.4s | 20.0-24.8s
  first_seen: 19.4s at (0.32, 0.74)   last_seen: 24.8s at (0.32, 0.76)
  gaps: 19.4-20.0s (last pos (0.32, 0.74))
Track 7 (mean_conf=0.23)
  visible: 6.8-6.8s | 20.2-24.8s
  first_seen: 6.8s at (0.28, 0.72)   last_seen: 24.8s at (0.29, 0.80)
  gaps: 6.8-20.2s (last pos (0.28, 0.72))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

[Tracking results] query="power outlet"  video_length=25.0s  tracker_fps=5
Track 0 (mean_conf=0.53)
  visible: 0.0-1.4s | 2.0-3.0s | 4.2-15.4s
  first_seen: 0.0s at (0.60, 0.65)   last_seen: 15.4s at (0.61, 0.64)
  gaps: 1.4-2.0s (last pos (0.59, 0.65)) | 3.0-4.2s (last pos (0.60, 0.65))
Track 3 (mean_conf=0.24)
  visible: 0.0-1.4s | 2.6-2.6s | 3.2-3.4s | 4.0-12.2s
  first_seen: 0.0s at (0.57, 0.65)   last_seen: 12.2s at (0.57, 0.65)
  gaps: 1.4-2.6s (last pos (0.57, 0.65)) | 2.6-3.2s (last pos (0.57, 0.65)) | 3.4-4.0s (last pos (0.57, 0.65))
Track 43 (mean_conf=0.26)
  visible: 15.4-15.6s | 17.4-18.0s | 19.0-24.8s
  first_seen: 15.4s at (0.60, 0.67)   last_seen: 24.8s at (0.61, 0.68)
  gaps: 15.6-17.4s (last pos (0.60, 0.67)) | 18.0-19.0s (last pos (0.61, 0.64))
Track 37 (mean_conf=0.26)
  visible: 12.4-12.4s | 17.4-17.6s | 19.0-24.8s
  first_seen: 12.4s at (0.60, 0.62)   last_seen: 24.8s at (0.61, 0.72)
  gaps: 12.4-17.4s (last pos (0.60, 0.62)) | 17.6-19.0s (last pos (0.61, 0.72))
Track 2 (mean_conf=0.23)
  visible: 0.0-0.0s | 3.2-3.2s | 4.2-4.6s | 5.6-5.8s | 6.8-10.2s | 11.0-11.4s | 12.0-12.2s | 15.6-15.6s
  first_seen: 0.0s at (0.61, 0.67)   last_seen: 15.6s at (0.60, 0.68)
  gaps: 0.0-3.2s (last pos (0.61, 0.67)) | 3.2-4.2s (last pos (0.61, 0.66)) | 4.6-5.6s (last pos (0.61, 0.65)) | 5.8-6.8s (last pos (0.61, 0.65)) | 10.2-11.0s (last pos (0.61, 0.65)) | 11.4-12.0s (last pos (0.61, 0.66)) | 12.2-15.6s (last pos (0.61, 0.65))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 14 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_correct_A_wrong / 3cc4b6a2cf1b

范围：test；可表达：False；视频：charades_D0V0Y。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "3cc4b6a2cf1b",
  "video_id": "charades_D0V0Y",
  "format": "ordering_3",
  "question": "Put the following events for wooden door in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it leaves the frame"
    },
    {
      "label": "B",
      "event_text": "it disappears for good"
    },
    {
      "label": "C",
      "event_text": "it gets partly hidden"
    }
  ]
}
```

真值：`['C', 'B', 'A']`。A解析：`['C', 'A', 'B']`；B解析：`['C', 'B', 'A']`。

A 原始输出：

```text
C, A, B
```

B 原始输出：

```text
C, B, A
```

完整轨迹文本：

```text
[Tracking results] query="wooden door"  video_length=34.0s  tracker_fps=5
Track 0 (mean_conf=0.80)
  visible: 0.0-12.4s
  first_seen: 0.0s at (0.37, 0.50)   last_seen: 12.4s at (0.28, 0.48)
  gaps: none
Track 22 (mean_conf=0.62)
  visible: 15.4-22.4s
  first_seen: 15.4s at (0.74, 0.52)   last_seen: 22.4s at (0.93, 0.54)
  gaps: none
Track 1 (mean_conf=0.45)
  visible: 9.6-15.2s
  first_seen: 9.6s at (0.77, 0.47)   last_seen: 15.2s at (0.75, 0.50)
  gaps: none
Track 51 (mean_conf=0.71)
  visible: 24.8-27.2s
  first_seen: 24.8s at (0.45, 0.42)   last_seen: 27.2s at (0.22, 0.38)
  gaps: none
Track 83 (mean_conf=0.32)
  visible: 28.2-31.2s | 32.0-32.2s | 33.4-33.6s
  first_seen: 28.2s at (0.70, 0.19)   last_seen: 33.6s at (0.55, 0.06)
  gaps: 31.2-32.0s (last pos (0.65, 0.04)) | 32.2-33.4s (last pos (0.57, 0.06))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 39 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_correct_A_wrong / d663925de846

范围：test；可表达：False；视频：perception_test_video_4932。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "d663925de846",
  "video_id": "perception_test_video_4932",
  "format": "ordering_3",
  "question": "Put the following events for bottle in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it gets fully hidden"
    },
    {
      "label": "B",
      "event_text": "it comes back into view"
    },
    {
      "label": "C",
      "event_text": "it gets partly hidden"
    }
  ]
}
```

真值：`['A', 'B', 'C']`。A解析：`['C', 'B', 'A']`；B解析：`['A', 'B', 'C']`。

A 原始输出：

```text
C, B, A
```

B 原始输出：

```text
A, B, C
```

完整轨迹文本：

```text
[Tracking results] query="bottle"  video_length=28.8s  tracker_fps=5
Track 1 (mean_conf=0.60)
  visible: 0.0-4.8s | 5.6-9.2s | 9.8-12.4s | 13.4-20.0s | 21.2-28.6s
  first_seen: 0.0s at (0.38, 0.25)   last_seen: 28.6s at (0.38, 0.25)
  gaps: 4.8-5.6s (last pos (0.38, 0.25)) | 9.2-9.8s (last pos (0.38, 0.25)) | 12.4-13.4s (last pos (0.37, 0.25)) | 20.0-21.2s (last pos (0.38, 0.25))
Track 0 (mean_conf=0.64)
  visible: 0.0-3.0s | 3.6-5.2s | 6.4-9.2s | 9.8-12.6s | 13.4-20.6s
  first_seen: 0.0s at (0.30, 0.26)   last_seen: 20.6s at (0.29, 0.23)
  gaps: 3.0-3.6s (last pos (0.30, 0.26)) | 5.2-6.4s (last pos (0.29, 0.26)) | 9.2-9.8s (last pos (0.30, 0.26)) | 12.6-13.4s (last pos (0.29, 0.23))
Track 39 (mean_conf=0.58)
  visible: 8.6-8.6s | 9.6-12.0s | 16.4-20.0s | 21.2-24.4s | 25.0-28.6s
  first_seen: 8.6s at (0.51, 0.23)   last_seen: 28.6s at (0.50, 0.23)
  gaps: 8.6-9.6s (last pos (0.51, 0.23)) | 12.0-16.4s (last pos (0.50, 0.23)) | 20.0-21.2s (last pos (0.50, 0.23)) | 24.4-25.0s (last pos (0.48, 0.21))
Track 2 (mean_conf=0.57)
  visible: 0.0-4.6s | 5.4-7.6s | 8.2-8.4s | 9.0-9.2s | 13.0-16.2s
  first_seen: 0.0s at (0.51, 0.23)   last_seen: 16.2s at (0.51, 0.23)
  gaps: 4.6-5.4s (last pos (0.51, 0.23)) | 7.6-8.2s (last pos (0.51, 0.23)) | 8.4-9.0s (last pos (0.50, 0.18)) | 9.2-13.0s (last pos (0.50, 0.23))
Track 68 (mean_conf=0.64)
  visible: 21.4-28.6s
  first_seen: 21.4s at (0.31, 0.26)   last_seen: 28.6s at (0.30, 0.26)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 19 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_correct_A_wrong / f69bd688d550

范围：test；可表达：False；视频：charades_FZBK6。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "f69bd688d550",
  "video_id": "charades_FZBK6",
  "format": "ordering_4",
  "question": "Put the following events for man in dark shirt in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it leaves the frame"
    },
    {
      "label": "B",
      "event_text": "it enters the frame"
    },
    {
      "label": "C",
      "event_text": "it gets partly hidden"
    },
    {
      "label": "D",
      "event_text": "it comes back into view"
    }
  ]
}
```

真值：`['B', 'C', 'D', 'A']`。A解析：`['D', 'B', 'C', 'A']`；B解析：`['B', 'C', 'D', 'A']`。

A 原始输出：

```text
D, B, C, A
```

B 原始输出：

```text
B, C, D, A
```

完整轨迹文本：

```text
[Tracking results] query="man in dark shirt"  video_length=20.2s  tracker_fps=5
Track 0 (mean_conf=0.22)
  visible: 1.4-1.6s | 2.2-2.8s
  first_seen: 1.4s at (0.53, 0.52)   last_seen: 2.8s at (0.58, 0.50)
  gaps: 1.6-2.2s (last pos (0.54, 0.52))
Track 4 (mean_conf=0.21)
  visible: 6.0-7.0s
  first_seen: 6.0s at (0.50, 0.50)   last_seen: 7.0s at (0.50, 0.50)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_wrong_A_correct / 67b7fcd55020

范围：test；可表达：True；视频：charades_DYVUY。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "67b7fcd55020",
  "video_id": "charades_DYVUY",
  "format": "ordering_3",
  "question": "Put the following events for wooden cabinets in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it disappears for good"
    },
    {
      "label": "B",
      "event_text": "it leaves the frame"
    },
    {
      "label": "C",
      "event_text": "it first shows up"
    }
  ]
}
```

真值：`['C', 'A', 'B']`。A解析：`['C', 'A', 'B']`；B解析：`['C', 'B', 'A']`。

A 原始输出：

```text
C, A, B
```

B 原始输出：

```text
C, B, A
```

完整轨迹文本：

```text
[Tracking results] query="wooden cabinets"  video_length=30.2s  tracker_fps=5
Track 1 (mean_conf=0.27)
  visible: 0.4-0.4s | 1.0-1.2s | 2.2-2.6s | 3.6-4.4s | 5.0-8.6s | 9.2-9.2s | 9.8-19.4s | 20.2-20.4s | 21.2-24.8s
  first_seen: 0.4s at (0.18, 0.18)   last_seen: 24.8s at (0.73, 0.32)
  gaps: 0.4-1.0s (last pos (0.18, 0.18)) | 1.2-2.2s (last pos (0.51, 0.16)) | 2.6-3.6s (last pos (0.31, 0.15)) | 4.4-5.0s (last pos (0.27, 0.19)) | 8.6-9.2s (last pos (0.35, 0.20)) | 9.2-9.8s (last pos (0.09, 0.12)) | 19.4-20.2s (last pos (0.44, 0.23)) | 20.4-21.2s (last pos (0.45, 0.24))
Track 7 (mean_conf=0.27)
  visible: 2.6-2.6s | 4.0-4.0s | 5.0-5.2s | 5.8-6.0s | 6.6-6.6s | 7.2-7.2s | 8.6-8.6s | 9.6-21.0s | 21.8-25.6s
  first_seen: 2.6s at (0.38, 0.33)   last_seen: 25.6s at (0.80, 0.54)
  gaps: 2.6-4.0s (last pos (0.38, 0.33)) | 4.0-5.0s (last pos (0.34, 0.36)) | 5.2-5.8s (last pos (0.39, 0.36)) | 6.0-6.6s (last pos (0.34, 0.38)) | 6.6-7.2s (last pos (0.34, 0.37)) | 7.2-8.6s (last pos (0.37, 0.36)) | 8.6-9.6s (last pos (0.37, 0.38)) | 21.0-21.8s (last pos (0.44, 0.43))
Track 19 (mean_conf=0.26)
  visible: 1.4-1.4s | 10.0-20.4s | 21.2-21.2s | 22.6-22.8s | 23.6-27.8s
  first_seen: 1.4s at (0.43, 0.39)   last_seen: 27.8s at (0.50, 0.58)
  gaps: 1.4-10.0s (last pos (0.43, 0.39)) | 20.4-21.2s (last pos (0.35, 0.49)) | 21.2-22.6s (last pos (0.36, 0.49)) | 22.8-23.6s (last pos (0.38, 0.47))
Track 8 (mean_conf=0.25)
  visible: 0.6-1.0s | 1.6-1.6s | 2.6-6.4s | 7.0-8.6s | 10.0-10.6s | 13.6-16.8s | 17.4-22.6s | 23.2-23.2s | 25.0-25.0s
  first_seen: 0.6s at (0.15, 0.69)   last_seen: 25.0s at (0.55, 0.75)
  gaps: 1.0-1.6s (last pos (0.28, 0.64)) | 1.6-2.6s (last pos (0.12, 0.67)) | 6.4-7.0s (last pos (0.13, 0.66)) | 8.6-10.0s (last pos (0.14, 0.66)) | 10.6-13.6s (last pos (0.18, 0.57)) | 16.8-17.4s (last pos (0.18, 0.65)) | 22.6-23.2s (last pos (0.28, 0.63)) | 23.2-25.0s (last pos (0.32, 0.73))
Track 28 (mean_conf=0.24)
  visible: 10.2-13.8s | 14.6-17.4s | 18.4-19.0s | 19.6-19.6s | 21.2-21.6s | 22.6-24.6s
  first_seen: 10.2s at (0.42, 0.39)   last_seen: 24.6s at (0.72, 0.51)
  gaps: 13.8-14.6s (last pos (0.41, 0.39)) | 17.4-18.4s (last pos (0.44, 0.41)) | 19.0-19.6s (last pos (0.45, 0.41)) | 19.6-21.2s (last pos (0.45, 0.42)) | 21.6-22.6s (last pos (0.48, 0.43))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 25 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_wrong_A_correct / a77b0193c8c5

范围：test；可表达：False；视频：charades_SX07Q。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "a77b0193c8c5",
  "video_id": "charades_SX07Q",
  "format": "ordering_3",
  "question": "Put the following events for black leggings in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it leaves the frame"
    },
    {
      "label": "B",
      "event_text": "it disappears for good"
    },
    {
      "label": "C",
      "event_text": "it gets partly hidden"
    }
  ]
}
```

真值：`['C', 'B', 'A']`。A解析：`['C', 'B', 'A']`；B解析：`['C', 'A', 'B']`。

A 原始输出：

```text
C, B, A
```

B 原始输出：

```text
C, A, B
```

完整轨迹文本：

```text
[Tracking results] query="black leggings"  video_length=48.2s  tracker_fps=5
Track 1 (mean_conf=0.56)
  visible: 0.0-1.4s | 2.0-45.4s
  first_seen: 0.0s at (0.52, 0.50)   last_seen: 45.4s at (0.53, 0.52)
  gaps: 1.4-2.0s (last pos (0.50, 0.51))
Track 0 (mean_conf=0.26)
  visible: 0.0-16.6s | 17.8-21.0s | 21.8-24.4s
  first_seen: 0.0s at (0.55, 0.81)   last_seen: 24.4s at (0.50, 0.73)
  gaps: 16.6-17.8s (last pos (0.50, 0.73)) | 21.0-21.8s (last pos (0.50, 0.74))
Track 9 (mean_conf=0.28)
  visible: 24.8-42.2s | 42.8-46.0s
  first_seen: 24.8s at (0.50, 0.73)   last_seen: 46.0s at (0.50, 0.80)
  gaps: 42.2-42.8s (last pos (0.50, 0.73))
Track 14 (mean_conf=0.44)
  visible: 46.6-48.0s
  first_seen: 46.6s at (0.50, 0.74)   last_seen: 48.0s at (0.52, 0.74)
  gaps: none
Track 12 (mean_conf=0.27)
  visible: 46.4-48.0s
  first_seen: 46.4s at (0.48, 0.28)   last_seen: 48.0s at (0.51, 0.28)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 6 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_wrong_A_correct / c6b08d647eeb

范围：test；可表达：False；视频：charades_YJ2CM。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "c6b08d647eeb",
  "video_id": "charades_YJ2CM",
  "format": "ordering_3",
  "question": "Put the following events for wooden cabinets in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it leaves the frame"
    },
    {
      "label": "B",
      "event_text": "it disappears for good"
    },
    {
      "label": "C",
      "event_text": "it gets partly hidden"
    }
  ]
}
```

真值：`['C', 'B', 'A']`。A解析：`['C', 'B', 'A']`；B解析：`['A', 'B', 'C']`。

A 原始输出：

```text
C, B, A
```

B 原始输出：

```text
A, B, C
```

完整轨迹文本：

```text
[Tracking results] query="wooden cabinets"  video_length=22.8s  tracker_fps=5
Track 0 (mean_conf=0.46)
  visible: 0.0-20.8s
  first_seen: 0.0s at (0.10, 0.21)   last_seen: 20.8s at (0.10, 0.22)
  gaps: none
Track 10 (mean_conf=0.28)
  visible: 0.2-7.0s | 8.4-9.4s | 11.0-11.8s | 13.2-16.4s | 19.2-21.2s
  first_seen: 0.2s at (0.07, 0.92)   last_seen: 21.2s at (0.07, 0.91)
  gaps: 7.0-8.4s (last pos (0.07, 0.92)) | 9.4-11.0s (last pos (0.07, 0.92)) | 11.8-13.2s (last pos (0.07, 0.92)) | 16.4-19.2s (last pos (0.07, 0.92))
Track 2 (mean_conf=0.23)
  visible: 0.0-1.2s | 1.8-6.8s | 7.4-7.4s | 8.0-9.8s | 10.4-10.8s | 12.4-12.6s | 13.2-13.2s | 15.0-15.2s | 15.8-15.8s | 16.6-22.6s
  first_seen: 0.0s at (0.91, 0.19)   last_seen: 22.6s at (0.91, 0.20)
  gaps: 1.2-1.8s (last pos (0.91, 0.20)) | 6.8-7.4s (last pos (0.91, 0.20)) | 7.4-8.0s (last pos (0.91, 0.20)) | 9.8-10.4s (last pos (0.91, 0.19)) | 10.8-12.4s (last pos (0.91, 0.20)) | 12.6-13.2s (last pos (0.91, 0.20)) | 13.2-15.0s (last pos (0.91, 0.20)) | 15.2-15.8s (last pos (0.91, 0.20)) | 15.8-16.6s (last pos (0.91, 0.20))
Track 18 (mean_conf=0.26)
  visible: 17.0-19.0s | 21.0-22.6s
  first_seen: 17.0s at (0.74, 0.28)   last_seen: 22.6s at (0.74, 0.28)
  gaps: 19.0-21.0s (last pos (0.74, 0.28))
Track 3 (mean_conf=0.21)
  visible: 0.0-0.0s | 1.8-2.0s | 5.2-5.2s | 20.8-21.4s
  first_seen: 0.0s at (0.50, 0.50)   last_seen: 21.4s at (0.50, 0.50)
  gaps: 0.0-1.8s (last pos (0.50, 0.50)) | 2.0-5.2s (last pos (0.50, 0.50)) | 5.2-20.8s (last pos (0.50, 0.50))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 3 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_wrong_A_correct / f18d0beedb14

范围：test；可表达：False；视频：charades_9O0NP。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "f18d0beedb14",
  "video_id": "charades_9O0NP",
  "format": "ordering_3",
  "question": "Put the following events for paper towel roll in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it gets fully hidden"
    },
    {
      "label": "B",
      "event_text": "it gets partly hidden"
    },
    {
      "label": "C",
      "event_text": "it disappears for good"
    }
  ]
}
```

真值：`['B', 'C', 'A']`。A解析：`['B', 'C', 'A']`；B解析：`['B', 'A', 'C']`。

A 原始输出：

```text
B, C, A
```

B 原始输出：

```text
B, A, C
```

完整轨迹文本：

```text
[Tracking results] query="paper towel roll"  video_length=30.8s  tracker_fps=5
Track 0 (mean_conf=0.44)
  visible: 0.0-11.4s | 12.0-12.4s
  first_seen: 0.0s at (0.84, 0.60)   last_seen: 12.4s at (0.90, 0.58)
  gaps: 11.4-12.0s (last pos (0.84, 0.59))
Track 77 (mean_conf=0.38)
  visible: 17.6-17.8s | 18.4-22.6s | 23.4-30.6s
  first_seen: 17.6s at (0.81, 0.42)   last_seen: 30.6s at (0.67, 0.40)
  gaps: 17.8-18.4s (last pos (0.81, 0.42)) | 22.6-23.4s (last pos (0.72, 0.39))
Track 1 (mean_conf=0.26)
  visible: 0.0-2.0s | 2.6-3.0s | 3.8-3.8s | 4.4-4.4s | 6.0-6.2s | 6.8-6.8s | 7.4-7.4s | 8.8-9.0s | 9.6-9.6s | 12.6-13.0s | 13.8-14.4s | 15.6-16.2s | 16.8-17.2s | 18.6-18.6s | 22.6-22.6s | 26.8-28.8s | 29.4-29.4s
  first_seen: 0.0s at (0.97, 0.47)   last_seen: 29.4s at (0.65, 0.41)
  gaps: 2.0-2.6s (last pos (0.97, 0.49)) | 3.0-3.8s (last pos (0.97, 0.48)) | 3.8-4.4s (last pos (0.98, 0.46)) | 4.4-6.0s (last pos (0.97, 0.46)) | 6.2-6.8s (last pos (0.97, 0.45)) | 6.8-7.4s (last pos (0.97, 0.47)) | 7.4-8.8s (last pos (0.97, 0.48)) | 9.0-9.6s (last pos (0.97, 0.47)) | 9.6-12.6s (last pos (0.97, 0.45)) | 13.0-13.8s (last pos (0.87, 0.45)) | 14.4-15.6s (last pos (0.71, 0.41)) | 16.2-16.8s (last pos (0.81, 0.42)) | 17.2-18.6s (last pos (0.83, 0.42)) | 18.6-22.6s (last pos (0.78, 0.41)) | 22.6-26.8s (last pos (0.69, 0.40)) | 28.8-29.4s (last pos (0.67, 0.40))
Track 3 (mean_conf=0.28)
  visible: 6.0-6.4s | 11.2-15.4s | 16.0-16.4s | 17.4-18.2s | 18.8-20.4s | 22.2-22.2s | 24.8-24.8s | 25.4-25.4s | 30.2-30.6s
  first_seen: 6.0s at (0.66, 0.59)   last_seen: 30.6s at (0.74, 0.54)
  gaps: 6.4-11.2s (last pos (0.67, 0.60)) | 15.4-16.0s (last pos (0.72, 0.52)) | 16.4-17.4s (last pos (0.78, 0.55)) | 18.2-18.8s (last pos (0.83, 0.55)) | 20.4-22.2s (last pos (0.75, 0.53)) | 22.2-24.8s (last pos (0.80, 0.53)) | 24.8-25.4s (last pos (0.77, 0.53)) | 25.4-30.2s (last pos (0.78, 0.52))
Track 79 (mean_conf=0.27)
  visible: 23.6-25.6s | 26.2-26.2s | 27.0-27.0s | 27.6-29.0s | 30.2-30.6s
  first_seen: 23.6s at (0.98, 0.11)   last_seen: 30.6s at (0.96, 0.09)
  gaps: 25.6-26.2s (last pos (0.98, 0.08)) | 26.2-27.0s (last pos (0.99, 0.07)) | 27.0-27.6s (last pos (0.99, 0.07)) | 29.0-30.2s (last pos (0.97, 0.10))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 32 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## Order / B_wrong_A_correct / 73409fad889f

范围：dev supplemental; not held-out example；可表达：False；视频：perception_test_video_3483。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "73409fad889f",
  "video_id": "perception_test_video_3483",
  "format": "ordering_3",
  "question": "Put the following events for orange ball in order from earliest to latest.",
  "events": [
    {
      "label": "A",
      "event_text": "it gets partly hidden"
    },
    {
      "label": "B",
      "event_text": "it comes back into view"
    },
    {
      "label": "C",
      "event_text": "it gets fully hidden"
    }
  ]
}
```

真值：`['C', 'B', 'A']`。A解析：`['C', 'B', 'A']`；B解析：`['A', 'B', 'C']`。

A 原始输出：

```text
C, B, A
```

B 原始输出：

```text
A, B, C
```

完整轨迹文本：

```text
[Tracking results] query="orange ball"  video_length=35.0s  tracker_fps=5
Track 1 (mean_conf=0.52)
  visible: 0.0-1.2s | 3.2-3.2s | 5.2-6.6s | 7.8-8.2s | 10.0-10.0s | 10.6-16.0s | 18.4-20.6s | 21.2-21.2s | 24.2-30.8s
  first_seen: 0.0s at (0.49, 0.69)   last_seen: 30.8s at (0.48, 0.58)
  gaps: 1.2-3.2s (last pos (0.48, 0.67)) | 3.2-5.2s (last pos (0.48, 0.68)) | 6.6-7.8s (last pos (0.47, 0.65)) | 8.2-10.0s (last pos (0.48, 0.64)) | 10.0-10.6s (last pos (0.47, 0.61)) | 16.0-18.4s (last pos (0.47, 0.57)) | 20.6-21.2s (last pos (0.48, 0.55)) | 21.2-24.2s (last pos (0.47, 0.57))
Track 84 (mean_conf=0.50)
  visible: 32.8-34.8s
  first_seen: 32.8s at (0.49, 0.58)   last_seen: 34.8s at (0.47, 0.57)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 1 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## ReID / B_wrong_A_correct / 32119de6d447

范围：test；可表达：True；视频：perception_test_video_9369。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "32119de6d447",
  "video_id": "perception_test_video_9369",
  "format": "sp",
  "question": "After the red lid comes back into view, is it the same lid as before, or a different one?",
  "statement_A": "the lid that comes back is a different one",
  "statement_B": "the lid that comes back is the same one as before"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A. the lid that comes back is a different one
```

完整轨迹文本：

```text
[Tracking results] query="red lid"  video_length=29.6s  tracker_fps=5
Track 0 (mean_conf=0.51)
  visible: 0.0-29.4s
  first_seen: 0.0s at (0.29, 0.74)   last_seen: 29.4s at (0.31, 0.75)
  gaps: none
Track 24 (mean_conf=0.28)
  visible: 9.6-17.6s | 18.8-21.4s | 22.0-24.2s | 26.0-29.4s
  first_seen: 9.6s at (0.48, 0.25)   last_seen: 29.4s at (0.48, 0.25)
  gaps: 17.6-18.8s (last pos (0.48, 0.25)) | 21.4-22.0s (last pos (0.47, 0.25)) | 24.2-26.0s (last pos (0.48, 0.25))
Track 2 (mean_conf=0.30)
  visible: 0.0-2.6s | 3.2-3.2s | 10.8-15.6s | 16.2-17.2s | 17.8-18.6s
  first_seen: 0.0s at (0.40, 0.66)   last_seen: 18.6s at (0.37, 0.58)
  gaps: 2.6-3.2s (last pos (0.41, 0.65)) | 3.2-10.8s (last pos (0.40, 0.66)) | 15.6-16.2s (last pos (0.37, 0.58)) | 17.2-17.8s (last pos (0.37, 0.58))
Track 37 (mean_conf=0.34)
  visible: 20.6-29.4s
  first_seen: 20.6s at (0.65, 0.46)   last_seen: 29.4s at (0.65, 0.46)
  gaps: none
Track 38 (mean_conf=0.34)
  visible: 20.8-29.4s
  first_seen: 20.8s at (0.65, 0.32)   last_seen: 29.4s at (0.65, 0.34)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 19 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## ReID / B_wrong_A_correct / c54586ea15fd

范围：test；可表达：True；视频：charades_4Y1AW。

模型可见问题 / 选项 / 事件：

```json
{
  "qa_id": "c54586ea15fd",
  "video_id": "charades_4Y1AW",
  "format": "sp",
  "question": "After the yellow plastic bag comes back into view, is it the same bag as before, or a different one?",
  "statement_A": "the bag that comes back is a different one",
  "statement_B": "the bag that comes back is the same one as before"
}
```

真值：`B`。A解析：`B`；B解析：`A`。

A 原始输出：

```text
B
```

B 原始输出：

```text
A. the bag that comes back is a different one
```

完整轨迹文本：

```text
[Tracking results] query="yellow plastic bag"  video_length=34.2s  tracker_fps=5
Track 0 (mean_conf=0.56)
  visible: 0.0-13.8s
  first_seen: 0.0s at (0.55, 0.47)   last_seen: 13.8s at (0.97, 0.65)
  gaps: none
Track 59 (mean_conf=0.52)
  visible: 27.2-27.6s | 30.0-34.0s
  first_seen: 27.2s at (0.98, 0.60)   last_seen: 34.0s at (0.96, 0.75)
  gaps: 27.6-30.0s (last pos (0.99, 0.55))
Track 33 (mean_conf=0.24)
  visible: 18.0-18.0s | 19.0-24.0s | 25.0-27.0s | 27.8-29.6s
  first_seen: 18.0s at (0.73, 0.62)   last_seen: 29.6s at (0.54, 0.64)
  gaps: 18.0-19.0s (last pos (0.73, 0.62)) | 24.0-25.0s (last pos (0.63, 0.73)) | 27.0-27.8s (last pos (0.53, 0.63))
Track 24 (mean_conf=0.30)
  visible: 18.0-18.0s | 20.0-20.4s | 21.0-21.0s | 21.8-22.6s | 23.2-23.2s | 25.0-27.0s | 27.8-28.6s | 29.2-29.2s
  first_seen: 18.0s at (0.65, 0.85)   last_seen: 29.2s at (0.46, 0.85)
  gaps: 18.0-20.0s (last pos (0.65, 0.85)) | 20.4-21.0s (last pos (0.60, 0.79)) | 21.0-21.8s (last pos (0.55, 0.83)) | 22.6-23.2s (last pos (0.49, 0.79)) | 23.2-25.0s (last pos (0.53, 0.90)) | 27.0-27.8s (last pos (0.46, 0.80)) | 28.6-29.2s (last pos (0.50, 0.89))
Track 56 (mean_conf=0.30)
  visible: 24.4-24.8s | 25.8-27.0s | 28.2-29.8s
  first_seen: 24.4s at (0.93, 0.97)   last_seen: 29.8s at (0.92, 0.89)
  gaps: 24.8-25.8s (last pos (0.93, 0.94)) | 27.0-28.2s (last pos (0.92, 0.89))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 22 additional short, low-confidence, or lower-ranked tracks were omitted.

```
