# =============================================================================
# Tokyo Smartphone Messenger ('Kidoku' / LINE-Style UI) & Furigana Ruby Helper
# Engine: Ren'Py 8.x (Drop-in .rpy script — zero external image dependencies!)
# Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
# License: Commercial Royalty-Free (Included in Tokyo VN SFX & Messenger Pro)
# =============================================================================
#
# QUICKSTART:
# 1. Copy `tokyo_messenger_and_ruby.rpy` into your Ren'Py project's `game/` folder.
# 2. Copy the 40 WAV folders (`01_school_chimes` .. `05_vn_messenger_and_jrpg_ui`)
#    into `game/audio/tokyo_sfx/`.
# 3. Call `jp_ruby("神保町", "じんぼうちょう")` anywhere in dialogue or chat text,
#    and use `TokyoChatSession` + `screen tokyo_phone_chat` for live phone scenes!
# =============================================================================

init offset = -2

default persistent.tokyo_show_furigana = True
default tokyo_read_receipt_label = "既読"  # Set to "Read" for English localization

init python:
    import time as _tokyo_time

    TOKYO_SFX_ROOT = "audio/tokyo_sfx/"

    TOKYO_SFX_MAP = {
        "kidoku_pop": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/25_messenger_kidoku_pop.wav",
        "send_swoosh": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/26_messenger_send_swoosh.wav",
        "sticker_bounce": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/27_messenger_sticker_bounce.wav",
        "typing_tick": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/28_messenger_typing_tick.wav",
        "desk_vibrate": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/29_smartphone_desk_vibrate.wav",
        "hover": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/34_ui_choice_hover_soft.wav",
        "confirm": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/35_ui_confirm_sparkle.wav",
        "affection_up": TOKYO_SFX_ROOT + "05_vn_messenger_and_jrpg_ui/38_vn_affection_up_chime.wav",
        "school_chime": TOKYO_SFX_ROOT + "01_school_chimes/01_school_chime_courtyard_westminster.wav",
        "fumikiri": TOKYO_SFX_ROOT + "03_trains_and_crossings/10_fumikiri_railroad_crossing_loop.wav",
    }

    def tokyo_play_sfx(key_or_path, channel="sound"):
        """Safely trigger a Tokyo SFX WAV if present in the Ren'Py archive/game dir."""
        resolved = TOKYO_SFX_MAP.get(key_or_path, key_or_path)
        if renpy.loadable(resolved):
            renpy.sound.play(resolved, channel=channel)

    def jp_ruby(kanji, reading):
        """Format Japanese Furigana using Ren'Py native {rb}/{rt} ruby text tags.

        Respects `persistent.tokyo_show_furigana` so players can toggle furigana
        ON/OFF in Preferences for accessibility or Japanese study!
        """
        k_str = str(kanji)
        r_str = str(reading)
        if not getattr(persistent, "tokyo_show_furigana", True) or not r_str:
            return k_str
        return "{rb}" + k_str + "{/rb}{rt}" + r_str + "{/rt}"

    class TokyoChatMessage(object):
        """Single entry in a TokyoChatSession feed (bubble, sticker, or divider)."""

        def __init__(
            self,
            kind="npc",
            sender="",
            text="",
            timestamp="23:42",
            kidoku=False,
            sticker_title="",
            sticker_glyph="",
            avatar_char="葵",
            avatar_bg="#3A6EA5",
        ):
            self.kind = kind  # "npc" | "player" | "divider"
            self.sender = sender
            self.text = text
            self.timestamp = timestamp
            self.kidoku = kidoku
            self.sticker_title = sticker_title
            self.sticker_glyph = sticker_glyph
            self.avatar_char = avatar_char
            self.avatar_bg = avatar_bg

    class TokyoChatSession(object):
        """Stateful controller for the `tokyo_phone_chat` smartphone overlay."""

        def __init__(self, title="水瀬 葵 (Aoi)", status_text="Online · Tokyo", clock_text="23:42"):
            self.title = title
            self.status_text = status_text
            self.clock_text = clock_text
            self.messages = []
            self.typing_active = False
            self.typing_sender = ""
            self.typing_avatar_char = "葵"
            self.typing_avatar_bg = "#3A6EA5"
            self.scroll_y = 1.0

        def add_divider(self, label_text):
            self.messages.append(TokyoChatMessage(kind="divider", text=label_text))
            renpy.restart_interaction()

        def receive(
            self,
            sender,
            text,
            timestamp=None,
            typing_sec=0.75,
            avatar_char="葵",
            avatar_bg="#3A6EA5",
        ):
            """Animate `...` typing indicator, then pop an incoming NPC bubble."""
            ts = timestamp or self.clock_text
            if typing_sec and typing_sec > 0.0:
                self.typing_active = True
                self.typing_sender = sender
                self.typing_avatar_char = avatar_char
                self.typing_avatar_bg = avatar_bg
                tokyo_play_sfx("typing_tick")
                renpy.restart_interaction()
                renpy.pause(typing_sec * 0.5, hard=False)
                tokyo_play_sfx("typing_tick")
                renpy.pause(typing_sec * 0.5, hard=False)
                self.typing_active = False

            self.messages.append(
                TokyoChatMessage(
                    kind="npc",
                    sender=sender,
                    text=text,
                    timestamp=ts,
                    avatar_char=avatar_char,
                    avatar_bg=avatar_bg,
                )
            )
            tokyo_play_sfx("kidoku_pop")
            renpy.restart_interaction()

        def send(self, text, timestamp=None, mark_kidoku=True, kidoku_delay=0.45):
            """Send player green bubble, then flip `既読` ('Read') receipt ON."""
            ts = timestamp or self.clock_text
            msg = TokyoChatMessage(
                kind="player",
                sender="Me",
                text=text,
                timestamp=ts,
                kidoku=False,
            )
            self.messages.append(msg)
            tokyo_play_sfx("send_swoosh")
            renpy.restart_interaction()

            if mark_kidoku:
                if kidoku_delay and kidoku_delay > 0.0:
                    renpy.pause(kidoku_delay, hard=False)
                msg.kidoku = True
                tokyo_play_sfx("kidoku_pop")
                renpy.restart_interaction()

        def send_sticker(self, sticker_glyph, sticker_title, is_player=True, timestamp=None):
            """Send an expressive Tokyo chat stamp / sticker with bounce SFX."""
            ts = timestamp or self.clock_text
            msg = TokyoChatMessage(
                kind="player" if is_player else "npc",
                sender="Me" if is_player else self.title,
                sticker_glyph=sticker_glyph,
                sticker_title=sticker_title,
                timestamp=ts,
                kidoku=is_player,
            )
            self.messages.append(msg)
            tokyo_play_sfx("sticker_bounce")
            renpy.restart_interaction()

        def ask_choice(self, choices, auto_send_reply=True, timestamp=None):
            """Present branching reply choices inside the phone drawer.

            `choices`: list of `(reply_display_text, return_value)` tuples.
            """
            selected_text, selected_value = renpy.call_screen(
                "tokyo_phone_chat",
                session=self,
                choices=choices,
                modal_mode=True,
            )
            if auto_send_reply and selected_text:
                self.send(selected_text, timestamp=timestamp)
            return selected_value


# -----------------------------------------------------------------------------
# Styles & ATL Transforms (Crisp Tokyo LINE-Inspired Dark/Slate Messenger)
# -----------------------------------------------------------------------------

style tokyo_chat_ruby is default:
    size 12
    color "#B8C4D6"
    yoffset -2

style tokyo_chat_text is default:
    size 20
    color "#141820"
    line_leading 8
    ruby_style style.tokyo_chat_ruby

style tokyo_chat_npc_text is tokyo_chat_text:
    color "#EDF2F8"

transform tokyo_bubble_pop_in:
    alpha 0.0
    yoffset 8
    zoom 0.96
    easeout 0.14 alpha 1.0 yoffset 0 zoom 1.0

transform tokyo_typing_dot_bounce(delay_t=0.0):
    alpha 0.35
    yoffset 0
    pause delay_t
    block:
        easein 0.24 alpha 1.0 yoffset -4
        easeout 0.24 alpha 0.35 yoffset 0
        pause 0.22
        repeat


# -----------------------------------------------------------------------------
# Main Smartphone Screen (`show screen tokyo_phone_chat(chat)` or `ask_choice`)
# -----------------------------------------------------------------------------

screen tokyo_phone_chat(session, choices=None, modal_mode=False, xalign_pos=0.88):
    modal modal_mode
    zorder 65

    frame:
        xalign xalign_pos
        yalign 0.5
        xsize 460
        ysize 820
        padding (14, 14)
        background Solid("#11151D")

        vbox:
            spacing 0
            xfill True
            yfill True

            # 1. Phone Status Bar (5G · Clock · Battery)
            frame:
                xfill True
                ysize 32
                padding (14, 4)
                background Solid("#181E29")
                hbox:
                    xfill True
                    text "[session.clock_text]" size 14 color "#C7D2E2" yalign 0.5
                    text "5G · 94%" size 13 color "#8E9CB2" xalign 1.0 yalign 0.5

            # 2. Messenger Room Header
            frame:
                xfill True
                ysize 58
                padding (16, 8)
                background Solid("#1F2735")
                hbox:
                    spacing 12
                    yalign 0.5
                    xfill True
                    text "‹" size 26 color "#9FB0C8" yalign 0.5
                    vbox:
                        yalign 0.5
                        text "[session.title]" size 19 bold True color "#F3F6FB"
                        text "[session.status_text]" size 12 color "#6BD65A"
                    textbutton "ふりがな":
                        xalign 1.0
                        yalign 0.5
                        text_size 12
                        text_color ("#6BD65A" if persistent.tokyo_show_furigana else "#7B879B")
                        background Solid("#2A3446")
                        padding (8, 4)
                        action ToggleField(persistent, "tokyo_show_furigana")

            # 3. Scrollable Conversation Feed
            viewport id "tokyo_chat_vp":
                xfill True
                ysize (530 if choices else 670)
                draggable True
                mousewheel True
                yinitial 1.0

                frame:
                    xfill True
                    padding (14, 14)
                    background Solid("#151A24")

                    vbox:
                        spacing 12
                        xfill True

                        for msg in session.messages:
                            if msg.kind == "divider":
                                frame:
                                    xalign 0.5
                                    padding (12, 4)
                                    background Solid("#222B3A")
                                    text "[msg.text]" size 12 color "#99A8BF"

                            elif msg.kind == "npc":
                                hbox:
                                    spacing 10
                                    xalign 0.0
                                    at tokyo_bubble_pop_in

                                    # Circular monogram badge
                                    frame:
                                        xsize 38
                                        ysize 38
                                        background Solid(msg.avatar_bg)
                                        text "[msg.avatar_char]" size 17 bold True color "#FFFFFF" align (0.5, 0.5)

                                    vbox:
                                        spacing 3
                                        if msg.sender:
                                            text "[msg.sender]" size 12 color "#96A5BC"
                                        hbox:
                                            spacing 6
                                            yalign 1.0
                                            if msg.sticker_title:
                                                frame:
                                                    padding (16, 12)
                                                    background Solid("#253042")
                                                    vbox:
                                                        spacing 4
                                                        xalign 0.5
                                                        text "[msg.sticker_glyph]" size 32 xalign 0.5
                                                        text "[msg.sticker_title]" size 13 color "#DCE6F5" xalign 0.5
                                            else:
                                                frame:
                                                    xmaximum 275
                                                    padding (13, 10)
                                                    background Solid("#253042")
                                                    text msg.text style "tokyo_chat_npc_text"
                                            text "[msg.timestamp]" size 11 color "#7D8CA3" yalign 1.0

                            elif msg.kind == "player":
                                hbox:
                                    spacing 6
                                    xalign 1.0
                                    at tokyo_bubble_pop_in

                                    # Authentic Japanese LINE layout: 既読 + HH:MM stacked to LEFT of green bubble!
                                    vbox:
                                        yalign 1.0
                                        spacing 1
                                        if msg.kidoku:
                                            text "[tokyo_read_receipt_label]" size 11 color "#8BC97E" xalign 1.0
                                        text "[msg.timestamp]" size 11 color "#7D8CA3" xalign 1.0

                                    if msg.sticker_title:
                                        frame:
                                            padding (16, 12)
                                            background Solid("#6BD65A")
                                            vbox:
                                                spacing 4
                                                xalign 0.5
                                                text "[msg.sticker_glyph]" size 32 color "#102212" xalign 0.5
                                                text "[msg.sticker_title]" size 13 bold True color "#102212" xalign 0.5
                                    else:
                                        frame:
                                            xmaximum 275
                                            padding (13, 10)
                                            background Solid("#7AD64E")
                                            text msg.text style "tokyo_chat_text"

                        # Live '...' Typing Indicator Row
                        if session.typing_active:
                            hbox:
                                spacing 10
                                xalign 0.0
                                frame:
                                    xsize 38
                                    ysize 38
                                    background Solid(session.typing_avatar_bg)
                                    text "[session.typing_avatar_char]" size 17 bold True color "#FFFFFF" align (0.5, 0.5)
                                frame:
                                    padding (16, 11)
                                    background Solid("#253042")
                                    hbox:
                                        spacing 5
                                        text "●" size 13 color "#9FB2CC" at tokyo_typing_dot_bounce(0.0)
                                        text "●" size 13 color "#9FB2CC" at tokyo_typing_dot_bounce(0.16)
                                        text "●" size 13 color "#9FB2CC" at tokyo_typing_dot_bounce(0.32)

            # 4. Bottom Reply Choice Tray or Input Composer Bar
            if choices:
                frame:
                    xfill True
                    ysize 196
                    padding (12, 10)
                    background Solid("#1B2230")
                    vbox:
                        spacing 8
                        xfill True
                        text "Select Reply / 返信を選択" size 12 color "#8FA0B8"
                        for reply_text, reply_val in choices:
                            button:
                                xfill True
                                padding (12, 9)
                                background Solid("#263145")
                                hover_background Solid("#32425C")
                                hovered Function(tokyo_play_sfx, "hover")
                                action Return((reply_text, reply_val))
                                text reply_text size 16 color "#EFF4FC" style "tokyo_chat_npc_text"
            else:
                frame:
                    xfill True
                    ysize 56
                    padding (14, 10)
                    background Solid("#1B2230")
                    hbox:
                        spacing 10
                        xfill True
                        yalign 0.5
                        text "Aa  Message..." size 14 color "#6C7A91" yalign 0.5
                        text "Send" size 14 bold True color "#6BD65A" xalign 1.0 yalign 0.5


# -----------------------------------------------------------------------------
# Drop-in Playable Example Scene (`call demo_tokyo_midnight_messenger`)
# -----------------------------------------------------------------------------

label demo_tokyo_midnight_messenger:
    $ tokyo_play_sfx("school_chime", channel="sound")
    $ chat = TokyoChatSession(title="水瀬 葵 (Aoi)", status_text="Online · 放送室", clock_text="17:16")
    show screen tokyo_phone_chat(chat)

    $ chat.add_divider("Today · After School (放課後)")
    $ aoi_msg_1 = jp_ruby("放課後", "ほうかご") + "のチャイム鳴ったね！" + jp_ruby("神保町", "じんぼうちょう") + "の古本屋、まだ寄れる？"
    $ chat.receive("水瀬 葵", aoi_msg_1, timestamp="17:16", typing_sec=0.85)

    $ route_pick = chat.ask_choice([
        ("今すぐ校門に向かうよ！", "gate_fast"),
        ("駅前のコンビニで肉まん買って待ってて！", "konbini_stop"),
    ], timestamp="17:17")

    if route_pick == "gate_fast":
        $ chat.receive("水瀬 葵", "やった！じゃあ踏切の手前で待ってるね。", timestamp="17:17", typing_sec=0.75)
        $ tokyo_play_sfx("affection_up")
    else:
        $ chat.receive("水瀬 葵", "賛成！あたたかいお茶も買っておくね。", timestamp="17:18", typing_sec=0.75)

    $ chat.send_sticker("★彡", "On My Way! / 今行くよ！", is_player=True, timestamp="17:18")
    pause 1.0
    hide screen tokyo_phone_chat
    return
