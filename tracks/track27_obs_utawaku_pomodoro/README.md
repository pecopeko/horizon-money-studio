# OBS 歌枠セトリ＆作業ポモドーロ・時計 オールインワン透過オーバーレイ＋操作ドック (`track27_obs_utawaku_pomodoro`)

VTuber・YouTube・Twitch配信者向けの **OBS Studio ブラウザソース (`1920x1080` 透過)** ＆ **OBS カスタムブラウザドック** オールインワン製品です。

- **Live Interactive Preview & Hosted Lite OBS URLs**: <https://pecopeko.github.io/obs-utawaku-pomodoro-dock/>
- **BOOTH Product Page**: <https://pecopeko1011.booth.pm/>
- **Creator**: `peco` (`pecopeko`)

## Build & Test

```bash
# 1. Run JS Engine Unit Tests (node --test)
node --test tracks/track27_obs_utawaku_pomodoro/tests_js/engine.test.mjs

# 2. Build Lite & Pro standalone ZIPs (dist/*.zip is gitignored) + Public site/
python3 tracks/track27_obs_utawaku_pomodoro/build_packages.py

# 3. Render 3 1280x1280 BOOTH Showcase PNG Cards
python3 tracks/track27_obs_utawaku_pomodoro/generate_booth_images.py

# 4. Run Python Integration & Packaging Verification Suite
pytest tests/test_track27_obs_utawaku_pomodoro.py
```
