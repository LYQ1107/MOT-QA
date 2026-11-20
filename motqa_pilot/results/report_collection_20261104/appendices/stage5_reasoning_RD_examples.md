# 简短推理模板B：R/D答对与答错样例

各取测试集按qa_id排序的前5条；保留完整输出和轨迹文本。文中是否引用证据及引用是否准确，在主报告中人工核对；不把模型写出的解释视为其内部机制的证明。

## 答对：09ecc5ba1b9b

视频：perception_test_video_8872。问题：Before black leather couch comes back into view, was it fully blocked or did it left the frame?

A. black leather couch left the frame before coming back
B. black leather couch was fully blocked before coming back

真值：B；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

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

## 答对：128d74ab4e21

视频：charades_M8NEU。问题：Before plastic chair comes back into view, was it fully blocked or did it left the frame?

A. plastic chair left the frame before coming back
B. plastic chair was fully blocked before coming back

真值：A；解析：A；解析失败：False。

完整模型输出：

```text
Answer: A
```

完整轨迹证据：

```text
[Tracking results] query="plastic chair"  video_length=30.2s  tracker_fps=5
Track 34 (mean_conf=0.85)
  visible: 20.8-30.0s
  first_seen: 20.8s at (0.06, 0.91)   last_seen: 30.0s at (0.33, 0.80)
  gaps: none
Track 7 (mean_conf=0.45)
  visible: 4.0-6.2s | 6.8-12.4s | 20.6-20.6s | 21.2-21.2s
  first_seen: 4.0s at (0.93, 0.97)   last_seen: 21.2s at (0.98, 0.82)
  gaps: 6.2-6.8s (last pos (0.72, 0.65)) | 12.4-20.6s (last pos (0.70, 0.85)) | 20.6-21.2s (last pos (0.90, 0.91))
Track 0 (mean_conf=0.78)
  visible: 0.0-3.8s | 4.4-4.8s
  first_seen: 0.0s at (0.24, 0.86)   last_seen: 4.8s at (0.03, 0.89)
  gaps: 3.8-4.4s (last pos (0.01, 0.94))
Track 13 (mean_conf=0.45)
  visible: 5.8-9.6s | 10.8-10.8s | 11.6-14.0s | 15.0-15.0s
  first_seen: 5.8s at (0.56, 0.77)   last_seen: 15.0s at (0.85, 0.97)
  gaps: 9.6-10.8s (last pos (0.39, 0.84)) | 10.8-11.6s (last pos (0.39, 0.84)) | 14.0-15.0s (last pos (0.93, 0.74))
Track 14 (mean_conf=0.46)
  visible: 10.4-10.4s | 15.8-15.8s | 16.4-16.8s | 17.4-17.4s | 18.4-20.8s
  first_seen: 10.4s at (0.76, 0.96)   last_seen: 20.8s at (0.97, 0.97)
  gaps: 10.4-15.8s (last pos (0.76, 0.96)) | 15.8-16.4s (last pos (0.76, 0.85)) | 16.8-17.4s (last pos (0.39, 0.80)) | 17.4-18.4s (last pos (0.43, 0.84))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 34 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## 答对：24773ab677ad

视频：charades_Y4IIO。问题：Before microwave comes back into view, was it fully blocked or did it left the frame?

A. microwave left the frame before coming back
B. microwave was fully blocked before coming back

真值：B；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

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

## 答对：298c2a249578

视频：charades_KO34N。问题：Before blue cloth comes back into view, was it fully blocked or did it leave the frame?

A. blue cloth left the frame before coming back
B. blue cloth was fully blocked before coming back

真值：B；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

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

## 答对：3a4d09c7aa6d

视频：charades_WI6NB。问题：Before wooden cabinets comes back into view, was it fully blocked or did it leave the frame?

A. wooden cabinets left the frame before coming back
B. wooden cabinets was fully blocked before coming back

真值：A；解析：A；解析失败：False。

完整模型输出：

```text
Answer: A
```

完整轨迹证据：

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

## 答错：061682ce31ac

视频：perception_test_video_6366。问题：Before white mug comes back into view, was it fully blocked or did it leave the frame?

A. white mug was fully blocked before coming back
B. white mug left the frame before coming back

真值：A；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

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

## 答错：0893a25082de

视频：perception_test_video_10764。问题：When the ring disappears, does it get fully blocked or leave the frame?

A. ring got fully blocked
B. ring left the frame

真值：A；解析：None；解析失败：True。

完整模型输出：

```text
Answer: B. ring left the frame
```

完整轨迹证据：

```text
[Tracking results] query="ring"  video_length=27.2s  tracker_fps=5
Track 0 (mean_conf=0.65)
  visible: 0.0-13.2s | 19.2-19.8s
  first_seen: 0.0s at (0.89, 0.88)   last_seen: 19.8s at (0.92, 0.76)
  gaps: 13.2-19.2s (last pos (0.76, 0.80))
Track 29 (mean_conf=0.53)
  visible: 15.0-19.0s | 20.0-25.2s
  first_seen: 15.0s at (0.90, 0.78)   last_seen: 25.2s at (0.93, 0.76)
  gaps: 19.0-20.0s (last pos (0.91, 0.80))
Track 28 (mean_conf=0.23)
  visible: 18.6-18.6s | 22.8-25.2s
  first_seen: 18.6s at (0.91, 0.81)   last_seen: 25.2s at (0.94, 0.72)
  gaps: 18.6-22.8s (last pos (0.91, 0.81))
Track 89 (mean_conf=0.44)
  visible: 26.4-27.0s
  first_seen: 26.4s at (0.82, 0.80)   last_seen: 27.0s at (0.83, 0.75)
  gaps: none
Track 22 (mean_conf=0.31)
  visible: 13.6-14.6s
  first_seen: 13.6s at (0.80, 0.51)   last_seen: 14.6s at (0.80, 0.52)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 22 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## 答错：093589b84207

视频：perception_test_video_9981。问题：When the glass cup disappears, does it get fully blocked or leave the frame?

A. glass cup got fully blocked
B. glass cup left the frame

真值：A；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

```text
[Tracking results] query="glass cup"  video_length=35.0s  tracker_fps=5
Track 20 (mean_conf=0.59)
  visible: 18.0-20.0s | 20.6-25.0s | 25.8-34.8s
  first_seen: 18.0s at (0.70, 0.61)   last_seen: 34.8s at (0.71, 0.61)
  gaps: 20.0-20.6s (last pos (0.72, 0.61)) | 25.0-25.8s (last pos (0.72, 0.47))
Track 1 (mean_conf=0.58)
  visible: 0.0-5.8s | 7.0-16.2s
  first_seen: 0.0s at (0.51, 0.61)   last_seen: 16.2s at (0.50, 0.61)
  gaps: 5.8-7.0s (last pos (0.50, 0.61))
Track 2 (mean_conf=0.50)
  visible: 0.0-8.2s | 9.2-13.8s | 15.0-17.6s | 20.2-20.2s
  first_seen: 0.0s at (0.68, 0.61)   last_seen: 20.2s at (0.69, 0.61)
  gaps: 8.2-9.2s (last pos (0.68, 0.61)) | 13.8-15.0s (last pos (0.67, 0.61)) | 17.6-20.2s (last pos (0.66, 0.62))
Track 0 (mean_conf=0.55)
  visible: 0.0-4.0s | 5.0-10.2s | 11.6-12.6s | 24.0-24.4s
  first_seen: 0.0s at (0.36, 0.61)   last_seen: 24.4s at (0.34, 0.61)
  gaps: 4.0-5.0s (last pos (0.35, 0.61)) | 10.2-11.6s (last pos (0.34, 0.60)) | 12.6-24.0s (last pos (0.34, 0.61))
Track 22 (mean_conf=0.49)
  visible: 18.6-18.8s | 20.6-20.6s | 21.8-26.6s | 28.4-29.6s
  first_seen: 18.6s at (0.34, 0.61)   last_seen: 29.6s at (0.54, 0.61)
  gaps: 18.8-20.6s (last pos (0.37, 0.61)) | 20.6-21.8s (last pos (0.53, 0.61)) | 26.6-28.4s (last pos (0.53, 0.61))
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 20 additional short, low-confidence, or lower-ranked tracks were omitted.

```

## 答错：0e9e33c81d1d

视频：charades_6B328。问题：Before striped socks comes back into view, was it fully blocked or did it leave the frame?

A. striped socks left the frame before coming back
B. striped socks was fully blocked before coming back

真值：A；解析：None；解析失败：True。

完整模型输出：

```text
Answer: B. striped socks was fully blocked before coming back
```

完整轨迹证据：

```text
[Tracking results] query="striped socks"  video_length=30.6s  tracker_fps=5
Track 0 (mean_conf=0.56)
  visible: 0.0-30.4s
  first_seen: 0.0s at (0.50, 0.80)   last_seen: 30.4s at (0.48, 0.80)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.

```

## 答错：0f868943c6b8

视频：perception_test_video_6360。问题：Before the plastic container comes back into view, was it fully blocked or did it left the frame?

A. plastic container was fully blocked before coming back
B. plastic container left the frame before coming back

真值：A；解析：B；解析失败：False。

完整模型输出：

```text
Answer: B
```

完整轨迹证据：

```text
[Tracking results] query="plastic container"  video_length=12.0s  tracker_fps=5
Track 0 (mean_conf=0.65)
  visible: 0.0-11.8s
  first_seen: 0.0s at (0.60, 0.62)   last_seen: 11.8s at (0.60, 0.61)
  gaps: none
Track 1 (mean_conf=0.56)
  visible: 0.0-9.0s | 10.4-10.4s
  first_seen: 0.0s at (0.51, 0.73)   last_seen: 10.4s at (0.52, 0.74)
  gaps: 9.0-10.4s (last pos (0.51, 0.73))
Track 4 (mean_conf=0.32)
  visible: 0.0-11.8s
  first_seen: 0.0s at (0.67, 0.47)   last_seen: 11.8s at (0.67, 0.46)
  gaps: none
Track 6 (mean_conf=0.25)
  visible: 0.0-9.2s | 10.0-10.0s | 10.6-11.8s
  first_seen: 0.0s at (0.47, 0.86)   last_seen: 11.8s at (0.47, 0.86)
  gaps: 9.2-10.0s (last pos (0.47, 0.85)) | 10.0-10.6s (last pos (0.47, 0.85))
Track 2 (mean_conf=0.36)
  visible: 0.0-6.0s
  first_seen: 0.0s at (0.44, 0.63)   last_seen: 6.0s at (0.43, 0.62)
  gaps: none
Note: Coordinates are normalized (x, y) box centers. Tracks may be fragmented,
and a short low-confidence track may be a false detection or a split of another track.
Note: 14 additional short, low-confidence, or lower-ranked tracks were omitted.

```

