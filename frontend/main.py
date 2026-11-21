"""CampusFix cross-role Kivy application. Run: python -m frontend.main."""

import os
from datetime import datetime
from threading import Thread
from urllib.parse import urlencode

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as color

API_BASE = os.getenv("CAMPUSFIX_API_BASE", "http://127.0.0.1:8000").rstrip("/")
BG = "#F5F6F0"
WHITE = "#FFFFFF"
INK = "#183B32"
MUTED = "#65786E"
HERO = "#153A31"
PRIMARY = "#173C32"
ACCENT = "#E0F69B"
LINE = "#DFE6DC"
PALE = "#EDF5E1"
NEUTRAL = "#F0F2EB"
ERROR = "#B02F45"

# Use one set of meaningful pictograms in the signboard and ticket lists.
CATEGORY_ICONS = {
    "Wi-Fi/IT": ("wifi", "#E5E9FC", INK),
    "Hostel": ("hostel", "#FBE9D8", INK),
    "Electrical": ("electrical", "#FFF0C6", INK),
    "Cleanliness": ("cleanliness", "#DCF2E6", INK),
    "Classroom": ("classroom", "#F8E1DB", INK),
    "Other": ("other", "#E8ECE9", INK),
}

STATUS_COLORS = {
    "Open": ("#EDF1F7", "#38506B"),
    "In Progress": ("#F9ECD1", "#735018"),
    "Resolved": ("#E0F2E7", "#1C6243"),
    "Reopened": ("#F2E9F9", "#6A3888"),
}


def send_json(method, path, expected, done, *, body=None, token=None):
    """Run the HTTP call in a worker and return its result on Kivy's UI thread."""
    def work():
        data, error = None, None
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = requests.request(
                method, API_BASE + path, json=body, headers=headers,
                timeout=(3, 8), allow_redirects=False,
            )
        except requests.RequestException:
            error = "connection"
        else:
            if response.status_code != expected:
                error = response.status_code
            else:
                try:
                    data = response.json()
                except ValueError:
                    error = "response"
        Clock.schedule_once(lambda _dt: done(data, error))

    Thread(target=work, daemon=True).start()


def readable_date(iso_value):
    if isinstance(iso_value, str):
        try:
            date = datetime.fromisoformat(iso_value).astimezone()
            return date.strftime("%d %b %Y").lstrip("0")
        except (ValueError, OverflowError):
            pass
    return ""


def readable_timestamp(iso_value):
    if isinstance(iso_value, str):
        try:
            timestamp = datetime.fromisoformat(iso_value).astimezone()
            return timestamp.strftime("%d %b %Y, %I:%M %p").lstrip("0")
        except (ValueError, OverflowError):
            pass
    return "Not available"


def paint(widget, fill, radius=16, stroke=None):
    """Draw a background that follows the widget on resize."""
    with widget.canvas.before:
        outline = None
        if stroke:
            Color(*color(stroke))
            outline = RoundedRectangle(radius=[dp(radius)])
        shade = Color(*color(fill))
        shape = RoundedRectangle(radius=[dp(max(0, radius - (1 if stroke else 0)))])

    def resize(*_):
        inset = dp(1) if stroke else 0
        if outline is not None:
            outline.pos, outline.size = widget.pos, widget.size
        shape.pos = (widget.x + inset, widget.y + inset)
        shape.size = (max(0, widget.width - 2 * inset), max(0, widget.height - 2 * inset))

    widget.bind(pos=resize, size=resize)
    resize()
    return shade


def words(text, size=15, tint=INK, bold=False, min_height=0):
    label = Label(
        text=text, font_size=sp(size), color=color(tint), bold=bold,
        halign="left", valign="middle", size_hint_y=None,
    )
    label.bind(
        width=lambda item, width: setattr(item, "text_size", (max(1, width), None)),
        texture_size=lambda item, value: setattr(item, "height", max(dp(min_height), value[1] + dp(2))),
    )
    label.height = dp(max(min_height, size + 4))
    return label


def column(gap=0):
    box = BoxLayout(orientation="vertical", spacing=dp(gap), size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    return box


def pill(text, width, fill, ink, height=28):
    label = Label(
        text=text, bold=True, color=color(ink), font_size=sp(12),
        size_hint=(None, None), size=(dp(width), dp(height)),
    )
    paint(label, fill, radius=height / 2)
    return label


def action(text, callback, *, fill=PRIMARY, ink=WHITE, height=48, width=None):
    button = Button(
        text=text, bold=True, font_size=sp(15), color=color(ink),
        disabled_color=color(MUTED), size_hint_y=None, height=dp(height),
        background_normal="", background_down="", background_disabled_normal="",
        background_color=(0, 0, 0, 0),
    )
    if width is not None:
        button.size_hint_x, button.width = None, dp(width)
    shade = paint(button, fill, radius=12)

    def state_changed(item, _value):
        shade.rgba = color(PALE if item.disabled else fill)
        if item.state == "down" and not item.disabled:
            shade.a = .78

    button.bind(state=state_changed, disabled=state_changed, on_release=callback)
    return button


def page(screen, max_width):
    """A centered column that scrolls when the device has less room."""
    scroller = ScrollView(do_scroll_x=False, bar_width=dp(3), scroll_type=["bars", "content"])
    anchor = AnchorLayout(anchor_x="center", anchor_y="top", size_hint_y=None)
    body = column(22)
    body.size_hint_x = None

    def resize(*_):
        gutter = dp(18 if scroller.width < dp(650) else 32)
        body.width = min(dp(max_width), max(dp(1), scroller.width - 2 * gutter))
        anchor.height = body.height + 2 * gutter
        anchor.padding = (0, gutter, 0, gutter)

    body.bind(height=resize)
    scroller.bind(width=resize)
    anchor.add_widget(body)
    scroller.add_widget(anchor)
    screen.add_widget(scroller)
    resize()
    return scroller, body


# Native vector accents keep the app self-contained on every platform.
ICON_PATHS = {
    "campus": (
        (3, 15, 12, 20, 21, 15, 3, 15),
        (5, 5, 19, 5), (7, 7, 7, 13), (12, 7, 12, 13), (17, 7, 17, 13),
    ),
    "wifi": (
        (3, 15, 6, 17.2, 9, 18.5, 12, 19, 15, 18.5, 18, 17.2, 21, 15),
        (6, 11.5, 9, 13.4, 12, 14, 15, 13.4, 18, 11.5),
        (9, 8, 12, 9, 15, 8), (11.7, 5, 12.3, 5),
    ),
    "classroom": (
        (4, 8, 4, 18, 20, 18, 20, 8, 4, 8),
        (9, 5, 15, 5), (12, 5, 12, 8),
    ),
    "power": ((13, 20, 5, 10, 11, 10, 10, 4, 19, 14, 13, 14, 13, 20),),
    "bell": ((5, 9, 5, 13, 7, 16, 7, 17, 9, 20, 15, 20, 17, 17,
              17, 16, 19, 13, 19, 9), (9, 6, 15, 6),
             (10, 5, 11, 4, 13, 4, 14, 5)),
}


def icon_tile(name, fill, ink, side=38):
    tile = Widget(size_hint=(None, None), size=(dp(side), dp(side)))
    paint(tile, fill, radius=12)
    with tile.canvas.after:
        Color(*color(ink))
        paths = [Line(points=[], width=dp(1.20)) for _ in ICON_PATHS[name]]

    def position(*_):
        unit = dp(21) / 24
        x0, y0 = tile.center_x - 12 * unit, tile.center_y - 12 * unit
        for line, coords in zip(paths, ICON_PATHS[name]):
            line.points = [offset + value * unit for pair in zip(coords[::2], coords[1::2])
                           for offset, value in zip((x0, y0), pair)]

    tile.bind(pos=position, size=position)
    position()
    return tile


class FixlineBrandMark(Widget):
    """Small, resolution-independent CampusFix logo: routed path + check."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        side = min(w, h)
        x += (w - side) / 2
        y += (h - side) / 2

        def point(a, b):
            return (x + side * a, y + side * b)

        with self.canvas:
            Color(*color(ACCENT))
            RoundedRectangle(pos=(x, y), size=(side, side), radius=[side * .24])
            Color(*color(HERO))
            # A single routed line suggests campus wayfinding and progress.
            Line(points=[*point(.70, .75), *point(.40, .75),
                         *point(.28, .63), *point(.28, .34), *point(.49, .34)],
                 width=max(dp(2.4), side * .078), cap='round', joint='round')
            Ellipse(pos=(x + side * .65, y + side * .70),
                    size=(side * .10, side * .10))
            # The check is the visual promise of CampusFix: resolved.
            Line(points=[*point(.50, .43), *point(.62, .31), *point(.83, .58)],
                 width=max(dp(2.6), side * .085), cap='round', joint='round')


class FixlineGlyph(Widget):
    """Draw pictograms as vectors (no emoji/fonts/image assets required)."""
    def __init__(self, kind, color=INK, **kwargs):
        super().__init__(**kwargs)
        self.kind, self.ink = kind, color
        self.bind(pos=self.draw, size=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        s = min(w, h)
        x += (w - s) / 2
        y += (h - s) / 2

        def p(a, b):
            return (x + a * s, y + b * s)

        def path(*coords, width=0.055, close=False):
            pts = []
            for a, b in coords:
                pts.extend(p(a, b))
            Line(points=pts + (pts[:2] if close else []), width=max(1.3, s * width),
                 cap='round', joint='round')

        with self.canvas:
            Color(*color(self.ink))
            if self.kind == 'wifi':
                for radius in (0.34, 0.23, 0.12):
                    Line(circle=(*p(.5, .22), s * radius, 42, 138),
                         width=max(1.2, s * .055), cap='round')
                Ellipse(pos=p(.45, .12), size=(s * .1, s * .1))
            elif self.kind == 'hostel':
                path((.14,.24),(.14,.73), width=.065)
                path((.14,.44),(.84,.44),(.84,.24), width=.065)
                path((.15,.57),(.79,.57),(.84,.49), width=.075)
                Line(rounded_rectangle=(*p(.24,.59),s*.2,s*.11,s*.03), width=max(1,s*.035))
            elif self.kind == 'electrical':
                path((.56,.89),(.25,.48),(.46,.48),(.39,.12),(.78,.60),(.54,.60),(.56,.89), width=.07)
            elif self.kind == 'cleanliness':
                path((.42,.82),(.59,.32),width=.055)
                path((.46,.30),(.77,.39),(.73,.16),(.52,.1),(.46,.30),width=.05)
                path((.20,.67),(.20,.85),width=.04)
                path((.11,.76),(.29,.76),width=.04)
                path((.19,.27),(.19,.42),width=.04)
                path((.12,.35),(.26,.35),width=.04)
            elif self.kind == 'classroom':
                Line(rounded_rectangle=(*p(.14,.39),s*.72,s*.42,s*.055),width=max(1.2,s*.045))
                path((.48,.38),(.48,.23),(.31,.12),width=.045)
                path((.48,.23),(.67,.12),width=.045)
                path((.30,.66),(.70,.66),width=.04)
                path((.30,.55),(.59,.55),width=.04)
            elif self.kind == 'other':
                for px in (.25,.5,.75):
                    Ellipse(pos=p(px-.07,.43),size=(s*.14,s*.14))
            elif self.kind == 'route':
                path((.17,.26),(.39,.26),(.39,.72),(.77,.72),width=.07)
                Ellipse(pos=p(.10,.19),size=(s*.14,s*.14))
                Ellipse(pos=p(.68,.63),size=(s*.18,s*.18))
            elif self.kind == 'check':
                Line(circle=(*p(.5,.5),s*.37),width=max(1.2,s*.045))
                path((.30,.50),(.44,.36),(.71,.67),width=.07)
            elif self.kind == 'wrench':
                Line(circle=(*p(.68,.70),s*.15,30,285),width=max(1.2,s*.06))
                path((.58,.58),(.20,.19),width=.09)
                Ellipse(pos=p(.11,.09),size=(s*.18,s*.18))
            elif self.kind == 'pin':
                Line(circle=(*p(.5,.61),s*.26,0,180),width=max(1.2,s*.05))
                path((.24,.60),(.50,.12),(.76,.60),width=.055)
                Ellipse(pos=p(.43,.55),size=(s*.14,s*.14))
            elif self.kind == 'bell':
                Line(circle=(*p(.5,.50),s*.29,20,160),width=max(1.2,s*.045))
                path((.22,.60),(.22,.28),(.78,.28),(.78,.60),width=.055)
                Ellipse(pos=p(.44,.12),size=(s*.12,s*.12))
            elif self.kind == 'arrow':
                path((.20,.5),(.79,.5),width=.07)
                path((.59,.72),(.80,.5),(.59,.28),width=.07)
            elif self.kind == 'back':
                path((.79,.5),(.20,.5),width=.07)
                path((.40,.72),(.19,.5),(.40,.28),width=.07)
            else:
                Line(circle=(*p(.5,.5),s*.35),width=max(1.2,s*.06))



def status_panel(message, glyph="route"):
    """Consistent, readable empty/loading/error surface across all workspaces.

    The icon supports recognition, while text carries the full meaning.
    """
    panel = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(94),
        spacing=dp(13), padding=(dp(16), dp(15)),
    )
    paint(panel, WHITE, radius=17, stroke=LINE)
    icon_slot = AnchorLayout(size_hint=(None, 1), width=dp(43))
    icon_back = AnchorLayout(size_hint=(None, None), size=(dp(43), dp(43)))
    paint(icon_back, PALE, radius=13)
    icon_back.add_widget(FixlineGlyph(
        glyph, color=PRIMARY, size_hint=(None, None), size=(dp(27), dp(27)),
    ))
    icon_slot.add_widget(icon_back)
    panel.add_widget(icon_slot)
    message_label = words(message, 14, MUTED, min_height=40)
    panel.add_widget(message_label)
    message_label.bind(height=lambda _w, h: setattr(
        panel, "height", max(dp(94), h + dp(30))
    ))
    return panel


def brand(sign_out=None):
    """Locked CampusFix identity: route/check symbol plus one compact name."""
    bar = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(52))
    logo_slot = AnchorLayout(size_hint_x=None, width=dp(50))
    logo_slot.add_widget(FixlineBrandMark(size_hint=(None,None), size=(dp(46), dp(46))))
    bar.add_widget(logo_slot)
    name_slot = AnchorLayout(anchor_x="left")
    brand_name = Label(text="CampusFix", font_size=sp(23), bold=True,
                       color=color(INK), halign="left", valign="middle")
    brand_name.bind(size=lambda label, _: setattr(label, "text_size", label.size))
    name_slot.add_widget(brand_name)
    bar.add_widget(name_slot)
    if sign_out is not None:
        bar.add_widget(action("Sign out", sign_out, fill=WHITE,
                              ink=PRIMARY, width=92, height=42))
    return bar


FIXLINE_CATEGORIES = (
    ("Wi-Fi/IT", "wifi", "Internet and devices", "#E5E9FC"),
    ("Hostel", "hostel", "Rooms and facilities", "#FBE9D8"),
    ("Electrical", "electrical", "Power, lights and fans", "#FFF0C6"),
    ("Cleanliness", "cleanliness", "Cleaning and hygiene", "#DCF2E6"),
    ("Classroom", "classroom", "Learning spaces", "#F8E1DB"),
    ("Other", "other", "Other campus issues", "#E8ECE9"),
)


class FixlineCategoryTile(ButtonBehavior, BoxLayout):
    """A single large, labelled pictogram. No icon-only ambiguity."""
    def __init__(self, label, icon_name, subtitle, fill, on_pick, **kwargs):
        super().__init__(orientation="vertical", padding=dp(13),
                         spacing=dp(7), **kwargs)
        shade = paint(self, fill, radius=18)
        self.bind(on_release=lambda _tile: on_pick(label))
        def press(_tile, state):
            shade.a = 0.72 if state == "down" else 1.0
        self.bind(state=press)
        header = BoxLayout(size_hint_y=None, height=dp(45))
        header.add_widget(FixlineGlyph(icon_name, size_hint_x=None, width=dp(45)))
        header.add_widget(Widget())
        arrow = FixlineGlyph("arrow", color="#5E7B6D", size_hint_x=None, width=dp(22))
        header.add_widget(arrow)
        self.add_widget(header)
        self.add_widget(words(label, 17, INK, bold=True, min_height=26))
        self.add_widget(words(subtitle, 12, MUTED, min_height=24))


def fixline_categories_grid(open_by_category):
    grid = GridLayout(cols=2, spacing=dp(11), size_hint_y=None,
                      row_default_height=dp(135), row_force_default=True)
    for category in FIXLINE_CATEGORIES:
        grid.add_widget(FixlineCategoryTile(*category, on_pick=open_by_category))

    def adapt(*_):
        cols = 3 if grid.width >= dp(760) else 2
        if grid.cols != cols:
            grid.cols = cols
        count = len(FIXLINE_CATEGORIES)
        rows = (count + cols - 1) // cols
        grid.height = dp(rows * 135 + (rows-1) * 11)
    grid.bind(width=adapt)
    adapt()
    return grid

def campus_map(hero):
    """A small campus illustration in the report card's spare desktop space."""
    motifs = (
        ("#3E4078", (
            (9, 44, 61, 77, 107, 56, 154, 84, 208, 53, 160, 21, 116, 41, 70, 12, 9, 44),
            (27, 34, 74, 61, 119, 39, 177, 71),
            (43, 25, 88, 52, 135, 30, 192, 61),
        )),
        ("#777BCE", (
            (44, 64, 44, 88, 72, 103, 99, 90, 99, 63, 72, 49, 44, 64),
            (44, 88, 72, 73, 99, 90),
            (72, 73, 72, 49),
            (52, 73, 61, 67, 61, 75, 52, 81, 52, 73),
            (81, 62, 91, 68, 91, 77, 81, 71, 81, 62),
            (125, 62, 125, 84, 146, 94, 168, 84, 168, 63, 146, 51, 125, 62),
            (125, 84, 146, 72, 168, 84),
            (146, 72, 146, 51),
        )),
        ("#CDC5FF", (
            (77, 38, 97, 28, 123, 44, 153, 30, 188, 49, 188, 82),
            (183, 50, 188, 47, 193, 50),
        )),
    )
    painted = []
    with hero.canvas.before:
        for tint, polygons in motifs:
            shade = Color(*color(tint))
            paths = [Line(points=[], width=dp(1.25)) for _ in polygons]
            painted.append((shade, paths, polygons))
        pin_fill = Color(*color(ACCENT))
        pin = Ellipse(pos=(0, 0), size=(1, 1))
        hole_fill = Color(*color(HERO))
        hole = Ellipse(pos=(0, 0), size=(1, 1))

    def place(*_):
        show = hero.width >= dp(660)
        for shade, _, _ in painted:
            shade.a = 1 if show else 0
        pin_fill.a = hole_fill.a = 1 if show else 0
        if not show:
            return
        unit = min(dp(1.60), hero.height / 153, hero.width * .36 / 217)
        x0, y0 = hero.right - dp(22) - 217 * unit, hero.center_y - 57 * unit
        for _, paths, polygons in painted:
            for line, coords in zip(paths, polygons):
                line.points = [offset + value * unit for pair in zip(coords[::2], coords[1::2])
                               for offset, value in zip((x0, y0), pair)]
        px, py = x0 + 188 * unit, y0 + 91 * unit
        pin.pos, pin.size = (px - 11 * unit, py - 11 * unit), (22 * unit, 22 * unit)
        hole.pos, hole.size = (px - 4 * unit, py - 4 * unit), (8 * unit, 8 * unit)

    hero.bind(pos=place, size=place)
    place()


class TicketRow(ButtonBehavior, BoxLayout):
    pass


def row_chevron():
    end = Widget(size_hint_x=None, width=dp(10))
    with end.canvas:
        Color(*color(MUTED))
        shape = Line(points=[], width=dp(1.15))

    def place(*_):
        x, y = end.center_x, end.center_y
        shape.points = (x - dp(2), y + dp(5), x + dp(2), y, x - dp(2), y - dp(5))

    end.bind(pos=place, size=place)
    return end


class NotificationBell(ButtonBehavior, BoxLayout):
    """Touch-friendly notification shortcut with an unread count."""

    def __init__(self, opened, **kwargs):
        super().__init__(orientation="horizontal", spacing=dp(7),
                         padding=(dp(9), dp(4)), size_hint=(None, None),
                         size=(dp(190), dp(46)), **kwargs)
        shade = paint(self, WHITE, radius=12, stroke=LINE)
        self.bind(state=lambda _w, state: setattr(
            shade, "rgba", color(PALE if state == "down" else WHITE)
        ), on_release=opened)
        tile = AnchorLayout(size_hint_x=None, width=dp(36))
        tile.add_widget(icon_tile("bell", PALE, PRIMARY, 34))
        self.add_widget(tile)
        self.label = Label(text="Notifications", font_size=sp(13),
                           color=color(INK), bold=True, halign="left",
                           valign="middle")
        self.label.bind(size=lambda label, _: setattr(label, "text_size", label.size))
        self.add_widget(self.label)

    def set_count(self, count):
        if isinstance(count, int) and count >= 0:
            self.label.text = f"Notifications · {min(count, 99)}{'+' if count > 99 else ''}"
        else:
            self.label.text = "Notifications"


class Dashboard(Screen):
    """Fixline student signboard + existing live complaints/notifications."""
    def __init__(self, open_form, sign_out, load_complaints, open_detail, open_all,
                 open_notifications, **kwargs):
        super().__init__(**kwargs)
        self.open_detail = open_detail
        _, body = page(self, 1020)
        body.add_widget(brand(sign_out))

        notification_row = BoxLayout(size_hint_y=None, height=dp(46))
        notification_row.add_widget(Widget())
        self.bell = NotificationBell(open_notifications)
        notification_row.add_widget(self.bell)
        body.add_widget(notification_row)
        body.add_widget(self.report_card())

        sign_section = column(11)
        heading = BoxLayout(size_hint_y=None, height=dp(38))
        title = AnchorLayout(anchor_x="left")
        title.add_widget(words("What needs fixing?", 24, bold=True))
        heading.add_widget(title)
        right = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(95))
        right.add_widget(words("TAP A SIGN", 11, MUTED, bold=True))
        heading.add_widget(right)
        sign_section.add_widget(heading)
        sign_section.add_widget(fixline_categories_grid(lambda name: open_form(None, name)))
        body.add_widget(sign_section)

        self.notice = words("", 14, "#22694A", bold=True)
        self.body = body

        recent = column(10)
        section = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
        title = AnchorLayout(anchor_x="left")
        title.add_widget(words("Follow your fixes", 23, bold=True))
        section.add_widget(title)
        section.add_widget(action("View all", open_all, fill=WHITE,
                                  ink=PRIMARY, height=34, width=96))
        recent.add_widget(section)
        self.tickets = column()
        paint(self.tickets, WHITE, radius=18, stroke=LINE)
        self.tickets.padding = (dp(13), dp(3))
        recent.add_widget(self.tickets)
        body.add_widget(recent)

    def set_unread_count(self, count):
        self.bell.set_count(count)

    def show_notice(self, message):
        self.notice.text = message
        if message and not self.notice.parent:
            self.body.add_widget(self.notice, index=1)
        elif not message and self.notice.parent:
            self.body.remove_widget(self.notice)

    def show_message(self, message):
        self.tickets.clear_widgets()
        self.tickets.add_widget(words(message, 14, MUTED, min_height=56))

    def show_complaints(self, rows):
        if not rows:
            self.show_message("No requests yet. Tap an issue sign to report one.")
            return
        self.tickets.clear_widgets()
        for i, item in enumerate(rows):
            if i:
                separator = Widget(size_hint_y=None, height=dp(1))
                paint(separator, LINE, radius=0)
                self.tickets.add_widget(separator)
            category = item["category_name"]
            icon, fill, ink = CATEGORY_ICONS.get(category, ("other", PALE, PRIMARY))
            info = f"#{item['id']}  ·  {category}"
            date = readable_date(item.get("created_at"))
            if date:
                info += f"  ·  {date}"
            self.tickets.add_widget(self.ticket_row(
                item["title"], info, item["status"], icon, fill, ink,
                lambda _row, ticket_id=item["id"]: self.open_detail(ticket_id),
            ))

    @staticmethod
    def report_card():
        """Compact introduction; actual status progress stays inside each ticket."""
        card = column(9)
        paint(card, HERO, radius=22)
        card.add_widget(words("THE CAMPUS HELPDESK", 12, ACCENT, bold=True))
        card.add_widget(words("See it. Report it. Fix it.", 29, WHITE, bold=True))
        card.add_widget(words("Choose a problem below. We'll help you track the fix.", 14, "#DFEBE0"))
        def adapt(*_):
            pad = dp(23 if card.width >= dp(650) else 17)
            card.padding = (pad, pad, pad, pad)
        card.bind(width=adapt)
        adapt()
        return card

    @staticmethod
    def ticket_row(title, info, status, icon, icon_fill, icon_ink, opened):
        row = TicketRow(size_hint_y=None, spacing=dp(8))
        shade = paint(row, WHITE, radius=11)
        row.bind(on_release=opened)
        row.bind(state=lambda _row, state: setattr(shade, "rgba", color(PALE if state == "down" else WHITE)))
        icon_slot = AnchorLayout(size_hint_x=None, width=dp(38))
        icon_back = AnchorLayout(size_hint=(None, None), size=(dp(38), dp(38)))
        paint(icon_back, icon_fill, radius=12)
        icon_back.add_widget(FixlineGlyph(
            icon, color=icon_ink, size_hint=(None, None), size=(dp(26), dp(26)),
        ))
        icon_slot.add_widget(icon_back)
        row.add_widget(icon_slot)

        details = column(2)
        details.add_widget(words(title, 15, bold=True))
        details.add_widget(words(info, 12, MUTED))
        left = AnchorLayout(anchor_x="left")
        left.add_widget(details)
        row.add_widget(left)

        fill, ink = STATUS_COLORS.get(status, (NEUTRAL, MUTED))
        right = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(94))
        right.add_widget(pill(status, 94, fill, ink))
        row.add_widget(right)
        row.add_widget(row_chevron())

        def fit(*_):
            row.height = max(dp(68), details.height + dp(19))

        details.bind(height=fit)
        fit()
        return row


class CategoryOption(SpinnerOption):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.height = dp(44)
        self.color = color(INK)
        self.font_size = sp(15)
        self.background_normal = self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        shade = paint(self, PALE, radius=4)
        self.bind(state=lambda _button, state: setattr(
            shade, "rgba", color(LINE if state == "down" else PALE),
        ))


def input_field(hint, *, multiline=False, password=False):
    field = TextInput(
        hint_text=hint, multiline=multiline, password=password, font_size=sp(15), write_tab=False,
        size_hint_y=None, height=dp(112 if multiline else 48),
        foreground_color=color(INK), hint_text_color=color(MUTED),
        cursor_color=color(PRIMARY), padding=(dp(12), dp(12)),
        background_normal="", background_active="", background_color=(0, 0, 0, 0),
    )
    return field


def add_field(form, title, widget):
    group = column(5)
    group.add_widget(words(title, 14, bold=True))
    frame = AnchorLayout(size_hint_y=None, height=widget.height)
    shade = paint(frame, BG, radius=11, stroke=LINE)
    widget.bind(focus=lambda _item, focus: setattr(shade, "rgba", color(PALE if focus else BG)))
    frame.add_widget(widget)
    group.add_widget(frame)
    form.add_widget(group)



# Progress is computed from the current backend status. This is a visual summary;
# the separately-rendered Status History remains the source of event timestamps.
FIXLINE_STATUS_TEXT = {
    "Open": ("Reported", "Your issue has been received. It is waiting to be worked on.", 0),
    "In Progress": ("Being fixed", "Staff is working on this issue.", 1),
    "Resolved": ("Marked resolved", "The issue has been marked resolved. You can request another look if needed.", 2),
    "Reopened": ("Reopened", "Your request to reopen was accepted. The issue is back for review.", 1),
}


class FixlineTrack(Widget):
    """Resize-safe vector progress with three nodes, grounded in current status."""

    def __init__(self, status, **kwargs):
        super().__init__(size_hint_y=None, height=dp(49), **kwargs)
        self.status = status
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def redraw(self, *_):
        if self.width < 1 or self.height < 1:
            return
        active = FIXLINE_STATUS_TEXT.get(self.status, (None, None, 0))[2]
        xs = [self.x + self.width/6, self.center_x, self.x + self.width*5/6]
        y = self.center_y
        lime = color(ACCENT)
        faded = color("#5D8171")
        self.canvas.clear()
        with self.canvas:
            Color(*faded)
            Line(points=(xs[0], y, xs[2], y), width=dp(4.5), cap="round")
            if active > 0:
                Color(*lime)
                Line(points=(xs[0], y, xs[active], y), width=dp(4.5), cap="round")
            for index, x in enumerate(xs):
                selected = index <= active
                Color(*(lime if selected else faded))
                r = dp(11)
                Ellipse(pos=(x - r, y - r), size=(2*r, 2*r))
                Color(*color(HERO))
                inner = dp(4.2)
                Ellipse(pos=(x - inner, y - inner), size=(inner*2, inner*2))
                if index == active:
                    Color(*color(WHITE))
                    dot = dp(2.3)
                    Ellipse(pos=(x - dot, y - dot), size=(dot*2, dot*2))


def fixline_progress_card(status, updated_at=None):
    """At-a-glance journey; neither fabricates assignment nor historic events."""
    title, explanation, _ = FIXLINE_STATUS_TEXT.get(
        status, (str(status), "See the history below for recorded changes.", 0)
    )
    card = column(12)
    card.padding = (dp(18), dp(19), dp(18), dp(21))
    paint(card, HERO, radius=22)
    card.add_widget(words("YOUR REQUEST JOURNEY", 11, ACCENT, bold=True))
    card.add_widget(words(title, 25, WHITE, bold=True))
    card.add_widget(words(explanation, 14, "#DAE9DE"))
    card.add_widget(FixlineTrack(status))
    labels = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(2))
    middle = "Reopened" if status == "Reopened" else "Working"
    for index, text in enumerate(("Reported", middle, "Done")):
        label = Label(text=text, font_size=sp(12), bold=(index == FIXLINE_STATUS_TEXT.get(status, (None,None,0))[2]),
                      color=color(ACCENT if index == FIXLINE_STATUS_TEXT.get(status, (None,None,0))[2] else "#DBE7DE"),
                      halign="center", valign="middle")
        label.bind(size=lambda lbl, _: setattr(lbl, "text_size", lbl.size))
        labels.add_widget(label)
    card.add_widget(labels)
    if updated_at:
        card.add_widget(words(f"Last updated: {readable_timestamp(updated_at)}", 12, "#CBDBD0"))
    return card


class MyComplaintsScreen(Screen):
    """A visual, first-time-friendly student list using the existing authorized API."""
    FILTERS = (
        ("All", None, 70),
        ("Open", "Open", 78),
        ("Working", "In Progress", 103),
        ("Resolved", "Resolved", 107),
        ("Reopened", "Reopened", 112),
    )

    def __init__(self, back, reload_list, open_detail, **kwargs):
        super().__init__(**kwargs)
        self.open_detail = open_detail
        self.rows = []
        self.selected_status = None
        self.scroller, body = page(self, 920)
        body.add_widget(brand())
        body.add_widget(action("Back to campus", back, fill=WHITE, ink=PRIMARY, width=160, height=43))

        intro = column(6)
        intro.add_widget(words("YOUR REQUESTS", 11, PRIMARY, bold=True))
        intro.add_widget(words("Follow your fixes", 31, bold=True))
        intro.add_widget(words("Every report in one place. Tap a request to see its journey.", 14, MUTED))
        body.add_widget(intro)

        overview = column(10)
        overview.padding = (dp(15), dp(14), dp(15), dp(14))
        paint(overview, WHITE, radius=18, stroke=LINE)
        overview.add_widget(words("AT A GLANCE", 11, MUTED, bold=True))
        self.summary_row = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8))
        overview.add_widget(self.summary_row)
        body.add_widget(overview)

        filter_head = BoxLayout(size_hint_y=None, height=dp(34))
        left = AnchorLayout(anchor_x="left")
        left.add_widget(words("All your reports", 19, INK, bold=True))
        filter_head.add_widget(left)
        filter_head.add_widget(action("Refresh", reload_list, fill=WHITE, ink=PRIMARY, height=34, width=93))
        body.add_widget(filter_head)

        # A horizontal scroll keeps every filter reachable at phone width.
        filter_box = column(5)
        self.filter_hint = words("", 11, MUTED)
        filter_box.add_widget(self.filter_hint)
        self.filter_scroll = ScrollView(
            do_scroll_x=True, do_scroll_y=False, size_hint_y=None, height=dp(47),
            bar_width=dp(2), scroll_type=["bars", "content"],
        )
        self.filter_row = BoxLayout(size_hint_x=None, size_hint_y=None,
                                    height=dp(44), spacing=dp(7))
        self.filter_row.width = dp(sum(entry[2] for entry in self.FILTERS) + (len(self.FILTERS)-1)*7)
        self.filter_scroll.add_widget(self.filter_row)
        self.filter_scroll.bind(width=lambda _w, width: setattr(
            self.filter_hint, "text", "Swipe filters sideways to see more"
            if width < self.filter_row.width else "Filter your requests by status"
        ))
        filter_box.add_widget(self.filter_scroll)
        body.add_widget(filter_box)

        self.result_count = words("", 12, MUTED)
        body.add_widget(self.result_count)
        self.tickets = column()
        self.tickets.padding = (dp(13), dp(3))
        paint(self.tickets, WHITE, radius=18, stroke=LINE)
        body.add_widget(self.tickets)
        self.render_filters()
        self.render_summary()
        self.show_message("Loading your requests...")

    def render_filters(self):
        self.filter_row.clear_widgets()
        for title, status, width in self.FILTERS:
            active = status == self.selected_status
            self.filter_row.add_widget(action(
                title, lambda _button, selected=status: self.pick_filter(selected),
                fill=PRIMARY if active else WHITE,
                ink=WHITE if active else INK,
                height=43, width=width,
            ))

    def pick_filter(self, status):
        self.selected_status = status
        self.render_filters()
        self.render_rows()

    def render_summary(self):
        self.summary_row.clear_widgets()
        counts = (
            (sum(row.get("status") in ("Open", "Reopened") for row in self.rows), "Waiting", "#EDF1F7"),
            (sum(row.get("status") == "In Progress" for row in self.rows), "Working", "#FFF0C6"),
            (sum(row.get("status") == "Resolved" for row in self.rows), "Done", "#DCF2E6"),
        )
        for number, label, fill in counts:
            cell = BoxLayout(orientation="vertical", padding=(dp(8), dp(5)), spacing=dp(2))
            paint(cell, fill, radius=12)
            cell.add_widget(Label(text=str(number), color=color(INK), bold=True, font_size=sp(20)))
            cell.add_widget(Label(text=label, color=color(MUTED), font_size=sp(11)))
            self.summary_row.add_widget(cell)

    def show_message(self, message):
        self.tickets.clear_widgets()
        self.tickets.add_widget(status_panel(message, "route"))

    def set_rows(self, rows):
        self.rows = list(rows)
        self.render_summary()
        self.render_rows()

    def clear(self):
        self.rows = []
        self.selected_status = None
        self.render_filters()
        self.render_summary()
        self.result_count.text = ""
        self.show_message("Sign in to see your requests.")

    def render_rows(self):
        visible = [r for r in self.rows if self.selected_status is None or r.get("status") == self.selected_status]
        self.result_count.text = f"Showing {len(visible)} of {len(self.rows)} requests"
        if not visible:
            self.show_message(
                "Nothing reported yet. Go back and tap an issue sign." if not self.rows
                else "No requests in this category of progress. Try another filter."
            )
            return
        self.tickets.clear_widgets()
        for idx, item in enumerate(visible):
            if idx:
                divider = Widget(size_hint_y=None, height=dp(1))
                paint(divider, LINE, radius=0)
                self.tickets.add_widget(divider)
            category = item["category_name"]
            icon, fill, ink = CATEGORY_ICONS.get(category, ("other", PALE, PRIMARY))
            info = f"#{item['id']}  ·  {category}"
            date = readable_date(item.get("created_at"))
            if date:
                info += f"  ·  {date}"
            self.tickets.add_widget(Dashboard.ticket_row(
                item["title"], info, item["status"], icon, fill, ink,
                lambda _row, ticket_id=item["id"]: self.open_detail(ticket_id),
            ))


class NotificationsScreen(Screen):
    """List student alerts; opening an unread alert marks it read."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.scroller, body = page(self, 800)
        body.add_widget(brand())
        body.add_widget(action("Back to dashboard", client.open_dashboard,
                               fill=WHITE, ink=PRIMARY, width=185, height=44))
        intro = column(6)
        intro.add_widget(words("STUDENT PORTAL", 11, PRIMARY, bold=True))
        intro.add_widget(words("Notifications", 31, bold=True))
        intro.add_widget(words("Tap an update to open its complaint.", 15, MUTED))
        body.add_widget(intro)

        toolbar = BoxLayout(size_hint_y=None, height=dp(46))
        self.summary = Label(text="", font_size=sp(13), color=color(MUTED),
                             halign="left", valign="middle")
        self.summary.bind(size=lambda label, _: setattr(label, "text_size", label.size))
        toolbar.add_widget(self.summary)
        toolbar.add_widget(action("Refresh", lambda _b: client.load_notifications(),
                                  fill=WHITE, ink=PRIMARY, width=90, height=44))
        body.add_widget(toolbar)
        self.feed = column(9)
        body.add_widget(self.feed)
        self.show_message("Loading notifications...")

    def clear(self):
        self.summary.text = ""
        self.show_message("Sign in to see your notifications.")

    def show_message(self, message):
        self.feed.clear_widgets()
        self.feed.add_widget(status_panel(message, "bell"))

    def show_notifications(self, items):
        self.feed.clear_widgets()
        unread = sum(item.get("read_at") is None for item in items)
        self.summary.text = f"{len(items)} recent · {unread} unread in list"
        if not items:
            self.show_message("No notifications yet. Status updates will appear here.")
            return
        for item in items:
            fresh = item.get("read_at") is None
            fill = "#F2EFFE" if fresh else WHITE
            record = TicketRow(size_hint_y=None, spacing=dp(10),
                               padding=(dp(13), dp(12)))
            shade = paint(record, fill, radius=14, stroke=LINE)
            record.bind(
                state=lambda _row, state, shade=shade, fill=fill:
                    setattr(shade, "rgba", color(PALE if state == "down" else fill)),
                on_release=lambda _row, notification=item:
                    self.client.open_notification(notification),
            )
            icon_slot = AnchorLayout(size_hint_x=None, width=dp(37))
            icon_slot.add_widget(icon_tile("bell", PALE, PRIMARY, 36))
            record.add_widget(icon_slot)
            detail = column(5)
            detail.add_widget(words(f"Complaint #{item['complaint_id']}", 13,
                                    PRIMARY, bold=True))
            detail.add_widget(words(item.get("message") or "Status updated", 15))
            detail.add_widget(words(readable_timestamp(item.get("created_at")),
                                    12, MUTED))
            record.add_widget(detail)
            label = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(55))
            label.add_widget(pill("New" if fresh else "Read", 53,
                                  PRIMARY if fresh else NEUTRAL,
                                  WHITE if fresh else MUTED, height=27))
            record.add_widget(label)
            detail.bind(height=lambda _w, _h, detail=detail, record=record:
                        setattr(record, "height", max(dp(85), detail.height + dp(24))))
            record.height = max(dp(85), detail.height + dp(24))
            self.feed.add_widget(record)
        self.scroller.scroll_y = 1


class LoginScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.busy = False
        _, body = page(self, 480)
        body.add_widget(brand())
        intro = column(5)
        intro.add_widget(words("ONE CAMPUS. ONE PLACE.", 12, PRIMARY, bold=True))
        intro.add_widget(words("Sign in to CampusFix", 33, bold=True))
        intro.add_widget(words("Students report issues. Staff resolve them. Use your own account to continue.", 15, MUTED))
        body.add_widget(intro)

        form = column(13)
        form.padding = (dp(18), dp(18))
        paint(form, WHITE, radius=20, stroke=LINE)
        self.email = input_field("you@college.edu")
        self.password = input_field("Your account password", password=True)
        self.email.bind(on_text_validate=lambda _input: setattr(self.password, "focus", True))
        self.password.bind(on_text_validate=self.sign_in)
        add_field(form, "Email", self.email)
        add_field(form, "Password", self.password)
        self.sign_in_button = action("Sign in", self.sign_in, height=51)
        self.feedback = words("", 13, MUTED)
        form.add_widget(self.sign_in_button)
        form.add_widget(self.feedback)
        self.create_account_button = action(
            "Create a student account", self.client.open_registration,
            fill=PALE, ink=PRIMARY, height=48,
        )
        form.add_widget(self.create_account_button)
        body.add_widget(form)

    def show_message(self, text, *, error=False):
        self.feedback.color = color(ERROR if error else MUTED)
        self.feedback.text = text

    def set_busy(self, value):
        self.busy = value
        self.email.disabled = self.password.disabled = self.sign_in_button.disabled = value
        self.create_account_button.disabled = value
        self.sign_in_button.text = "Signing in..." if value else "Sign in"

    def sign_in(self, _widget):
        if self.busy:
            return
        email = self.email.text.strip()
        password = self.password.text
        if not email or not password:
            self.show_message("Enter your email and password.", error=True)
            return

        self.set_busy(True)
        self.show_message("")
        self.client.call(
            "POST", "/api/auth/login", 200, self.finish,
            body={"email": email, "password": password},
        )

    def finish(self, data, error):
        self.set_busy(False)
        self.password.text = ""
        if error == 401:
            self.show_message("That email or password did not match.", error=True)
        elif error == 422:
            self.show_message("Check that the email and password are entered correctly.", error=True)
        elif error == "connection":
            self.show_message("Could not reach CampusFix. Check that the backend is running.", error=True)
        elif error is not None or not isinstance(data, dict):
            self.show_message("CampusFix could not sign you in. Try again.", error=True)
        else:
            user = data.get("user")
            token = data.get("access_token")
            if not isinstance(user, dict) or not isinstance(token, str) or not token or not isinstance(user.get("id"), int):
                self.show_message("Could not read the sign-in response.", error=True)
            elif user.get("role") not in ("Student", "Staff", "Admin"):
                self.show_message("This account role is not supported.", error=True)
            else:
                self.client.signed_in(token, user)


class RegisterScreen(Screen):
    """Student self-registration using the existing FastAPI signup endpoint."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.busy = False
        _, body = page(self, 480)
        body.add_widget(brand())
        body.add_widget(action(
            "Back to sign in", self.client.back_to_login,
            fill=WHITE, ink=PRIMARY, width=170, height=44,
        ))
        intro = column(6)
        intro.add_widget(words("STUDENT REGISTRATION", 12, PRIMARY, bold=True))
        intro.add_widget(words("Create your account", 33, bold=True))
        intro.add_widget(words(
            "Join CampusFix to report and track your own campus issues.", 15, MUTED,
        ))
        body.add_widget(intro)

        form = column(13)
        form.padding = (dp(18), dp(18))
        paint(form, WHITE, radius=20, stroke=LINE)
        self.full_name = input_field("Your full name")
        self.email = input_field("you@college.edu")
        self.password = input_field("At least 8 characters", password=True)
        self.confirm_password = input_field("Re-enter your password", password=True)
        self.full_name.bind(on_text_validate=lambda _input: setattr(self.email, "focus", True))
        self.email.bind(on_text_validate=lambda _input: setattr(self.password, "focus", True))
        self.password.bind(on_text_validate=lambda _input: setattr(self.confirm_password, "focus", True))
        self.confirm_password.bind(on_text_validate=self.register)

        add_field(form, "Full name", self.full_name)
        add_field(form, "Email", self.email)
        add_field(form, "Password", self.password)
        add_field(form, "Confirm password", self.confirm_password)
        self.submit_button = action("Create student account", self.register, height=52)
        self.feedback = words("New accounts are created with the Student role.", 13, MUTED)
        form.add_widget(self.submit_button)
        form.add_widget(self.feedback)
        body.add_widget(form)

    def show_message(self, message, *, error=False):
        self.feedback.color = color(ERROR if error else MUTED)
        self.feedback.text = message

    def set_busy(self, busy):
        self.busy = busy
        for field in (self.full_name, self.email, self.password, self.confirm_password):
            field.disabled = busy
        self.submit_button.disabled = busy
        self.submit_button.text = "Creating account..." if busy else "Create student account"

    def register(self, _widget):
        if self.busy:
            return
        name = self.full_name.text.strip()
        email = self.email.text.strip()
        password = self.password.text
        confirmation = self.confirm_password.text

        if not name or len(name) > 120:
            self.show_message("Enter your name (up to 120 characters).", error=True)
            return
        if not email or "@" not in email or len(email) > 254:
            self.show_message("Enter a valid email address.", error=True)
            return
        if not 8 <= len(password) <= 128:
            self.show_message("Password must contain 8 to 128 characters.", error=True)
            return
        if password != confirmation:
            self.show_message("The two passwords do not match.", error=True)
            return

        self.set_busy(True)
        self.show_message("Creating your student account...")
        self.client.call(
            "POST", "/api/auth/register", 201, self.finish,
            body={"name": name, "email": email, "password": password},
        )

    def finish(self, data, error):
        self.set_busy(False)
        if error == 409:
            self.show_message("This email is already registered. Sign in instead.", error=True)
        elif error == 422:
            self.show_message("Please check your name, email and password.", error=True)
        elif error == "connection":
            self.show_message("Could not connect to CampusFix. Is FastAPI running?", error=True)
        elif error is not None or not isinstance(data, dict) or data.get("role") != "Student":
            self.show_message("Account could not be created. Please try again.", error=True)
        else:
            email = data.get("email", self.email.text.strip())
            self.full_name.text = ""
            self.email.text = ""
            self.password.text = ""
            self.confirm_password.text = ""
            self.client.registration_complete(email)


class ComplaintForm(Screen):
    def __init__(self, client, back, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.saving = False
        self.category_ids = {}
        self.selected_category_id = None
        self.pending_category_name = None
        self.loading = False
        self.scroller, body = page(self, 626)
        self.back_button = action("Back to dashboard", back, fill=WHITE, ink=PRIMARY, width=160, height=44)
        body.add_widget(self.back_button)

        heading = column(4)
        heading.add_widget(words("CAMPUS SERVICE REQUEST", 11, PRIMARY, bold=True))
        heading.add_widget(words("Report an issue", 34, bold=True))
        heading.add_widget(words("Give staff enough detail to find and fix the issue.", 15, MUTED))
        body.add_widget(heading)

        form = column(13)
        form.padding = (dp(17), dp(17))
        paint(form, WHITE, radius=20, stroke=LINE)
        form.add_widget(words("Issue details", 18, bold=True))
        self.title_input = input_field("e.g. Wi-Fi keeps dropping")
        self.location = input_field("e.g. Hostel B, Room 12")
        self.description = input_field("What happened? When did it start?", multiline=True)
        self.category = Spinner(
            text="Loading categories...", size_hint_y=None, height=dp(48),
            disabled=True, option_cls=CategoryOption, font_size=sp(15),
            color=color(INK), disabled_color=color(MUTED),
            background_normal="", background_down="", background_disabled_normal="",
            background_color=(0, 0, 0, 0),
        )
        paint(self.category, BG, radius=11, stroke=LINE)
        with self.category.canvas.after:
            Color(*color(MUTED))
            chevron = Line(points=[], width=1.1)

        def position_chevron(item, _value):
            x, y = item.right - dp(19), item.center_y
            chevron.points = (x - dp(5), y + dp(2), x, y - dp(3), x + dp(5), y + dp(2))

        self.category.bind(pos=position_chevron, size=position_chevron, text=self.select_category)
        position_chevron(self.category, None)
        self.retry = action("Retry categories", self.load_categories, fill=PALE, ink=PRIMARY, height=44)
        self.category_group = column(5)
        self.category_group.add_widget(words("Category", 14, bold=True))
        self.category_group.add_widget(self.category)

        add_field(form, "Issue title", self.title_input)
        form.add_widget(self.category_group)
        add_field(form, "Location", self.location)
        add_field(form, "Description", self.description)
        self.submit_button = action("Submit complaint", self.submit)
        self.feedback = words("After submitting, you can track it under My Complaints.", 13, MUTED)
        form.add_widget(self.submit_button)
        form.add_widget(self.feedback)
        body.add_widget(form)

    def prefill_category(self, name):
        """Apply a signboard choice, even when categories are still loading."""
        self.pending_category_name = name
        if name and name in self.category_ids:
            self.category.text = name
            self.selected_category_id = self.category_ids[name]
        elif not name and self.category_ids:
            self.category.text = "Select a category"
            self.selected_category_id = None
        elif name:
            self.selected_category_id = None

    def on_pre_enter(self, *_):
        if not self.category_ids:
            self.load_categories()
        self.scroller.scroll_y = 1

    def load_categories(self, *_):
        if self.loading:
            return
        self.loading = True
        self.category.disabled = True
        self.category.text = "Loading categories..."
        if self.retry.parent:
            self.category_group.remove_widget(self.retry)
        Thread(target=self.fetch_categories, daemon=True).start()

    def fetch_categories(self):
        try:
            response = requests.get(f"{API_BASE}/api/categories", timeout=5)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Expected a list of categories")
            items = {row["name"]: row["id"] for row in data}
            message = "" if items else "No categories available"
        except (requests.RequestException, ValueError, KeyError, TypeError):
            items, message = {}, "Categories unavailable"
        Clock.schedule_once(lambda _dt: self.show_categories(items, message))

    def show_categories(self, items, message):
        self.loading = False
        self.category_ids = items
        self.category.values = list(items)
        self.category.disabled = not items
        self.category.text = "Select a category" if items else message
        if self.pending_category_name and self.pending_category_name in items:
            self.category.text = self.pending_category_name
            self.selected_category_id = items[self.pending_category_name]
        if not items and not self.retry.parent:
            self.category_group.add_widget(self.retry)

    def select_category(self, _spinner, name):
        self.selected_category_id = self.category_ids.get(name)

    def submit(self, _button):
        if self.saving:
            return
        title = self.title_input.text.strip()
        location = self.location.text.strip()
        description = self.description.text.strip()
        if not all((title, self.selected_category_id is not None, location, description)):
            self.show_feedback("Enter a title, select a category, and add the location and description.", error=True)
            return
        if len(title) > 160 or len(location) > 180:
            self.show_feedback("Keep the title within 160 characters and the location within 180.", error=True)
            return

        self.set_saving(True)
        self.show_feedback("Saving to CampusFix...")
        self.client.call(
            "POST", "/api/complaints", 201, self.finish_submission,
            body={"title": title, "category_id": self.selected_category_id,
                  "location": location, "description": description},
            protected=True,
        )

    def show_feedback(self, text, *, error=False):
        self.feedback.color = color(ERROR if error else MUTED)
        self.feedback.text = text

    def set_saving(self, saving):
        self.saving = saving
        for item in (self.back_button, self.title_input, self.location, self.description, self.submit_button):
            item.disabled = saving
        self.category.disabled = saving or not self.category_ids
        self.submit_button.text = "Submitting..." if saving else "Submit complaint"

    def reset_form(self):
        self.title_input.text = self.location.text = self.description.text = ""
        self.category.is_open = False
        if self.category_ids:
            self.category.text = "Select a category"
        self.selected_category_id = None
        self.pending_category_name = None
        self.set_saving(False)
        self.show_feedback("After submitting, you can track it under My Complaints.")

    def finish_submission(self, data, error):
        self.set_saving(False)
        if error == 422:
            self.show_feedback("The server rejected the details. Check the fields and selected category.", error=True)
        elif error == 403:
            self.show_feedback("This account cannot submit student complaints.", error=True)
        elif error is not None or not isinstance(data, dict) or not isinstance(data.get("id"), int):
            self.show_feedback("Could not confirm the save. Check Recent complaints before retrying.", error=True)
        else:
            complaint_id = data["id"]
            self.reset_form()
            self.client.complaint_saved(complaint_id)


class ComplaintDetailScreen(Screen):
    def __init__(self, back, retry, client=None, **kwargs):
        super().__init__(**kwargs)
        self.retry = retry
        self.client = client
        self.ticket_id = None
        self.comment_version = 0
        self.comment_role = "staff" if self.name == "staff_detail" else "student"
        self.comment_feed = None
        self.comment_entry = None
        self.comment_button = None
        self.comment_notice = None
        self.reopen_feed = None
        self.reopen_editor = None
        self.reopen_button = None
        self.reopen_notice = None
        self.reopen_status = None
        self.scroller, body = page(self, 760)
        body.add_widget(brand())
        back_label = "Back to queue" if self.comment_role == "staff" else "Back to fixes"
        body.add_widget(action(back_label, back, fill=WHITE, ink=PRIMARY, width=160, height=44))
        self.content = column(14)
        body.add_widget(self.content)

    def clear(self):
        self.ticket_id = None
        self.comment_version += 1
        self.comment_feed = None
        self.comment_entry = None
        self.comment_button = None
        self.comment_notice = None
        self.reopen_feed = None
        self.reopen_editor = None
        self.reopen_button = None
        self.reopen_notice = None
        self.reopen_status = None
        self.content.clear_widgets()

    def show_loading(self, ticket_id):
        self.clear()
        self.ticket_id = ticket_id
        self.content.add_widget(words(f"COMPLAINT #{ticket_id}", 11, PRIMARY, bold=True))
        self.content.add_widget(words("Loading complaint...", 25, bold=True))
        self.scroller.scroll_y = 1

    def show_error(self, message, allow_retry=True):
        self.content.clear_widgets()
        self.content.add_widget(words("Complaint unavailable", 25, bold=True))
        self.content.add_widget(words(message, 15, MUTED))
        if allow_retry:
            self.content.add_widget(action("Try again", lambda _button: self.retry(self.ticket_id)))

    def show_complaint(self, complaint):
        self.content.clear_widgets()
        category = complaint["category_name"]
        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(10))
        id_slot = AnchorLayout(anchor_x="left")
        id_slot.add_widget(words(f"COMPLAINT #{complaint['id']}", 11, PRIMARY, bold=True))
        header.add_widget(id_slot)
        badge_slot = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(99))
        status = complaint["status"]
        fill, ink = STATUS_COLORS.get(status, (NEUTRAL, MUTED))
        badge_slot.add_widget(pill(status, 97, fill, ink))
        header.add_widget(badge_slot)
        self.content.add_widget(header)

        heading = column(4)
        heading.add_widget(words(complaint["title"], 31, bold=True))
        heading.add_widget(words(category, 15, MUTED))
        self.content.add_widget(heading)

        # A compact visual explanation before the detailed, real event history.
        self.content.add_widget(fixline_progress_card(status, complaint.get("updated_at")))

        details = column(13)
        details.padding = (dp(17), dp(17))
        paint(details, WHITE, radius=20, stroke=LINE)
        details.add_widget(words("Issue details", 18, bold=True))
        self.add_detail(details, "Location", complaint["location"])
        self.add_detail(details, "Description", complaint["description"])

        timestamps = column(13)
        timestamps.padding = (dp(17), dp(17))
        paint(timestamps, WHITE, radius=20, stroke=LINE)
        self.add_detail(timestamps, "Submitted", readable_timestamp(complaint.get("created_at")))
        self.add_detail(timestamps, "Last updated", readable_timestamp(complaint.get("updated_at")))
        self.content.add_widget(details)
        self.content.add_widget(timestamps)
        self.add_timeline(complaint.get("status_history", []))
        if self.comment_role == "student":
            self.add_reopen_panel(status)
        self.add_comments_panel()

    def add_reopen_panel(self, status):
        """Student-only request form and archived reopen decisions."""
        self.reopen_status = status
        panel = column(12)
        panel.padding = (dp(17), dp(17))
        paint(panel, WHITE, radius=20, stroke=LINE)
        panel.add_widget(words("Reopen requests", 19, bold=True))
        panel.add_widget(words(
            "If an issue was marked resolved incorrectly, ask staff to review it.",
            14, MUTED,
        ))
        self.reopen_feed = column(9)
        self.reopen_feed.add_widget(words("Loading request history...", 14, MUTED))
        panel.add_widget(self.reopen_feed)
        if status == "Resolved":
            panel.add_widget(words("Why is the issue still unresolved?", 14, bold=True))
            self.reopen_editor = TextInput(
                hint_text="Describe what still needs fixing...", multiline=True,
                font_size=sp(15), foreground_color=color(INK),
                hint_text_color=color(MUTED), background_normal="",
                background_active="", background_color=color(BG),
                cursor_color=color(PRIMARY), padding=(dp(12), dp(12)),
                size_hint_y=None, height=dp(110),
            )
            panel.add_widget(self.reopen_editor)
            self.reopen_button = action("Request reopen", self.send_reopen,
                                        fill=PRIMARY, ink=WHITE, height=50)
            self.reopen_button.disabled = True  # Wait for current request history.
            panel.add_widget(self.reopen_button)
        else:
            panel.add_widget(words(
                "Only a Resolved complaint can have a new reopen request.", 13, MUTED,
            ))
        self.reopen_notice = words("", 13, MUTED)
        panel.add_widget(self.reopen_notice)
        self.content.add_widget(panel)

    def show_reopen_requests(self, requests):
        if self.reopen_feed is None:
            return
        self.reopen_feed.clear_widgets()
        pending = False
        if not requests:
            self.reopen_feed.add_widget(words("No reopen requests yet.", 14, MUTED))
        for item in requests:
            state = str(item.get("status", "Unknown"))
            pending = pending or state == "Pending"
            card = column(6)
            card.padding = (dp(12), dp(12))
            paint(card, BG, radius=12)
            card.add_widget(words(f"{state}  ·  {readable_timestamp(item.get('created_at'))}",
                                  14, PRIMARY, bold=True))
            card.add_widget(words(str(item.get("reason") or ""), 14))
            if item.get("decided_at"):
                card.add_widget(words(f"Decision: {readable_timestamp(item['decided_at'])}",
                                      12, MUTED))
            self.reopen_feed.add_widget(card)
        if self.reopen_button is not None:
            self.reopen_button.disabled = pending
            if self.reopen_editor is not None:
                self.reopen_editor.disabled = pending
            if pending:
                self.set_reopen_notice("A request is pending Staff/Admin approval.")
            else:
                self.set_reopen_notice("")

    def show_reopen_error(self, message):
        if self.reopen_feed is not None:
            self.reopen_feed.clear_widgets()
            self.reopen_feed.add_widget(words(message, 14, ERROR))
        if self.reopen_button is not None:
            self.reopen_button.disabled = True
        self.set_reopen_notice("Refresh this complaint before requesting again.", error=True)

    def set_reopen_notice(self, message, error=False):
        if self.reopen_notice is not None:
            self.reopen_notice.text = message
            self.reopen_notice.color = color(ERROR if error else MUTED)

    def send_reopen(self, _button):
        if (self.reopen_editor is None or self.reopen_button is None
                or self.reopen_button.disabled or self.ticket_id is None):
            return
        reason = self.reopen_editor.text.strip()
        if not reason or len(reason) > 2000:
            self.set_reopen_notice("Write a reason between 1 and 2,000 characters.", error=True)
            return
        self.reopen_button.disabled = True
        self.set_reopen_notice("Submitting reopen request...")
        self.client.submit_reopen_request(self.ticket_id, reason)

    def add_comments_panel(self):
        """Reusable thread composer for student and assigned staff detail views."""
        panel = column(12)
        panel.padding = (dp(17), dp(17))
        paint(panel, WHITE, radius=20, stroke=LINE)
        panel.add_widget(words("Conversation", 19, bold=True))
        panel.add_widget(words("Replies are visible to this student and the assigned staff.", 13, MUTED))

        self.comment_feed = column(11)
        self.comment_feed.add_widget(words("Loading replies...", 14, MUTED))
        panel.add_widget(self.comment_feed)

        panel.add_widget(words("Add a reply", 13, MUTED, bold=True))
        self.comment_entry = TextInput(
            hint_text="Write a helpful update...", multiline=True,
            font_size=sp(15), foreground_color=color(INK),
            hint_text_color=color(MUTED), background_normal="",
            background_active="", background_color=color(BG),
            cursor_color=color(PRIMARY), padding=(dp(12), dp(12)),
            size_hint_y=None, height=dp(104),
        )
        panel.add_widget(self.comment_entry)
        self.comment_button = action(
            "Send reply", self.send_comment, fill=PRIMARY, ink=WHITE, height=48,
        )
        panel.add_widget(self.comment_button)
        self.comment_notice = words("", 13, MUTED)
        panel.add_widget(self.comment_notice)
        self.content.add_widget(panel)

    def send_comment(self, _button):
        if self.ticket_id is None or self.comment_entry is None or self.client is None:
            return
        message = self.comment_entry.text.strip()
        if not message:
            self.set_comment_notice("Write a reply before sending.", error=True)
            return
        if len(message) > 2000:
            self.set_comment_notice("Please keep the reply under 2,000 characters.", error=True)
            return
        self.comment_button.disabled = True
        self.set_comment_notice("Sending reply...")
        self.client.post_comment(self.ticket_id, self.comment_role, message)

    def set_comment_notice(self, message, error=False):
        if self.comment_notice is not None:
            self.comment_notice.text = message
            self.comment_notice.color = color(ERROR if error else MUTED)

    def show_comments(self, comments):
        if self.comment_feed is None:
            return
        self.comment_feed.clear_widgets()
        if not comments:
            self.comment_feed.add_widget(words(
                "No replies yet. Your conversation will appear here.", 14, MUTED,
            ))
            return
        for item in comments:
            entry = column(5)
            entry.padding = (dp(12), dp(11))
            paint(entry, BG, radius=12)
            author = str(item.get("author_name") or "Member")
            role = str(item.get("author_role") or "")
            when = readable_timestamp(item.get("created_at"))
            entry.add_widget(words(f"{author}  ·  {role}", 14, PRIMARY, bold=True))
            entry.add_widget(words(when, 12, MUTED))
            entry.add_widget(words(str(item.get("body") or ""), 15, INK))
            self.comment_feed.add_widget(entry)

    def show_comments_error(self, message):
        if self.comment_feed is None:
            return
        self.comment_feed.clear_widgets()
        self.comment_feed.add_widget(words(message, 14, ERROR))
        self.comment_feed.add_widget(action(
            "Retry replies", lambda _btn: self.client.load_comments(
                self.ticket_id, self.comment_role
            ), fill=WHITE, ink=PRIMARY, height=42,
        ))

    def add_timeline(self, events):
        """Show an accessible, chronological status history from the API."""
        timeline = column(13)
        timeline.padding = (dp(17), dp(17))
        paint(timeline, WHITE, radius=20, stroke=LINE)
        timeline.add_widget(words("Recorded status history", 18, bold=True))

        if not isinstance(events, list) or not events:
            timeline.add_widget(words(
                "No recorded events yet. Older changes may be unavailable.",
                14, MUTED,
            ))
        else:
            for position, event in enumerate(events):
                if not isinstance(event, dict):
                    continue
                old_status = event.get("old_status")
                new_status = event.get("new_status", "Unknown")
                description = (
                    "Complaint submitted" if old_status is None
                    else f"{old_status}  →  {new_status}"
                )
                item = column(5)
                row = BoxLayout(size_hint_y=None, height=dp(31), spacing=dp(7))
                title = AnchorLayout(anchor_x="left")
                title.add_widget(words(description, 15, bold=True))
                row.add_widget(title)
                fill, ink = STATUS_COLORS.get(new_status, (NEUTRAL, MUTED))
                tag = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(99))
                tag.add_widget(pill(new_status, 97, fill, ink))
                row.add_widget(tag)
                item.add_widget(row)
                by = event.get("changed_by_name") or "CampusFix"
                when = readable_timestamp(event.get("changed_at"))
                item.add_widget(words(f"{when}  ·  {by}", 13, MUTED))
                timeline.add_widget(item)
                if position < len(events) - 1:
                    line = Widget(size_hint_y=None, height=dp(1))
                    paint(line, LINE, radius=0)
                    timeline.add_widget(line)

        self.content.add_widget(timeline)

    @staticmethod
    def add_detail(container, label, value):
        group = column(3)
        group.add_widget(words(label, 13, MUTED, bold=True))
        group.add_widget(words(value, 15))
        container.add_widget(group)


class StaffDashboard(Screen):
    """Fixline Workbench: every visible ticket leads to a clear next action.

    The existing client supplies server-authorized, assigned-only records.
    """
    FILTERS = ("Unresolved", "All assigned")

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.rows = []
        self.scroller, body = page(self, 950)
        body.add_widget(brand(client.sign_out))

        # The staff hero is short and practical. No decorative fake metrics.
        hero = column(9)
        hero.padding = (dp(22), dp(21))
        paint(hero, HERO, radius=23)
        hero.add_widget(words("STAFF  /  WORKBENCH", 12, ACCENT, bold=True))
        hero.add_widget(words("Your next fix.", 31, WHITE, bold=True))
        hero.add_widget(words(
            "Open an assigned job, update its progress, and keep the student informed.",
            14, "#D7E6DB",
        ))
        path_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(9))
        for caption in ("Assigned", "Working", "Done"):
            slot = AnchorLayout(anchor_x="center")
            slot.add_widget(pill(caption, 90, "#315E4C", "#F4F8E9", 29))
            path_row.add_widget(slot)
        hero.add_widget(path_row)
        body.add_widget(hero)

        shortcuts = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        shortcuts.add_widget(action(
            "Review reopen requests", client.open_reopen_review,
            fill=ACCENT, ink=PRIMARY, height=54,
        ))
        shortcuts.add_widget(action(
            "Refresh", lambda _btn: self.client.load_staff_queue(),
            fill=WHITE, ink=PRIMARY, height=54, width=92,
        ))
        body.add_widget(shortcuts)

        heading = column(4)
        heading.add_widget(words("Assigned to you", 24, INK, bold=True))
        heading.add_widget(words(
            "Only your assigned requests appear here. Tap a card to open the job.",
            14, MUTED,
        ))
        body.add_widget(heading)

        controls = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.filter = Spinner(
            text=self.FILTERS[0], values=self.FILTERS,
            option_cls=CategoryOption, font_size=sp(14),
            color=color(INK), size_hint_x=None, width=dp(155),
            background_normal="", background_down="", background_color=(0, 0, 0, 0),
        )
        paint(self.filter, WHITE, radius=11, stroke=LINE)
        controls.add_widget(self.filter)
        self.count = Label(
            text="", font_size=sp(13), color=color(MUTED),
            halign="right", valign="middle",
        )
        self.count.bind(size=lambda item, _: setattr(item, "text_size", item.size))
        controls.add_widget(self.count)
        body.add_widget(controls)

        self.tickets = column(11)
        body.add_widget(self.tickets)
        self.filter.bind(text=lambda *_: self.client.load_staff_queue())
        self.show_message("Sign in to see your assigned requests.")

    def clear(self):
        self.rows = []
        self.count.text = ""
        self.show_message("Sign in to see your assigned requests.")

    def show_message(self, message):
        self.tickets.clear_widgets()
        self.tickets.add_widget(status_panel(message, "wrench"))

    def show_complaints(self, rows):
        self.rows = list(rows)
        self.count.text = f"{len(self.rows)} in view"
        if not rows:
            self.show_message(
                "You're all caught up here. Choose All assigned to see completed jobs, "
                "or check again after an Admin assigns work."
            )
            return

        self.tickets.clear_widgets()
        palette = {name: (glyph, fill) for name, glyph, _subtitle, fill in FIXLINE_CATEGORIES}
        for item in rows:
            # No client-side fake priorities or inferred deadlines.
            category = str(item.get("category_name") or "Other")
            glyph, category_fill = palette.get(category, ("other", NEUTRAL))
            status = str(item.get("status") or "Open")
            status_fill, status_ink = STATUS_COLORS.get(status, (NEUTRAL, MUTED))

            card = TicketRow(
                orientation="vertical", size_hint_y=None,
                padding=(dp(16), dp(14)), spacing=dp(8),
            )
            card.bind(minimum_height=card.setter("height"))
            shade = paint(card, WHITE, radius=19, stroke=LINE)
            card.bind(
                state=lambda _widget, state, layer=shade: setattr(
                    layer, "rgba", color(PALE if state == "down" else WHITE)
                ),
                on_release=lambda _widget, ticket_id=item["id"]:
                    self.client.open_staff_detail(ticket_id),
            )

            headline = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(11))
            mark = AnchorLayout(size_hint_x=None, width=dp(44))
            pictogram = FixlineGlyph(glyph, color=PRIMARY,
                                    size_hint=(None, None), size=(dp(25), dp(25)))
            glyph_bg = AnchorLayout(size_hint=(None, None), size=(dp(43), dp(43)))
            paint(glyph_bg, category_fill, radius=12)
            glyph_bg.add_widget(pictogram)
            mark.add_widget(glyph_bg)
            headline.add_widget(mark)
            info = column(2)
            info.add_widget(words(f"TICKET #{item['id']}", 11, MUTED, bold=True))
            info.add_widget(words(category, 15, INK, bold=True))
            headline.add_widget(info)
            open_label = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(58))
            open_label.add_widget(words("VIEW  ›", 12, PRIMARY, bold=True))
            headline.add_widget(open_label)
            card.add_widget(headline)

            card.add_widget(words(str(item.get("title") or "Untitled request"), 20, INK, bold=True))
            foot = BoxLayout(size_hint_y=None, height=dp(31), spacing=dp(7))
            foot.add_widget(pill(status, 112, status_fill, status_ink, 28))
            date = readable_date(item.get("created_at"))
            if date:
                date_box = AnchorLayout(anchor_x="right")
                date_box.add_widget(words(date, 12, MUTED))
                foot.add_widget(date_box)
            else:
                foot.add_widget(Widget())
            card.add_widget(foot)
            self.tickets.add_widget(card)


class StaffDetailScreen(ComplaintDetailScreen):
    """Put the next permitted staff action immediately after the progress line."""
    NEXT = {"Open": "In Progress", "In Progress": "Resolved", "Reopened": "In Progress"}
    ACTION_LABELS = {
        "In Progress": "Start working on this",
        "Resolved": "Mark this issue resolved",
    }

    def __init__(self, client, **kwargs):
        self.client = client
        self.status_button = None
        self.status_feedback = None
        self.next_status = None
        super().__init__(client.back_to_staff_queue, client.open_staff_detail,
                         client=client, **kwargs)

    def clear(self):
        super().clear()
        self.status_button = None
        self.status_feedback = None
        self.next_status = None

    def show_complaint(self, complaint):
        super().show_complaint(complaint)
        status = complaint.get("status")
        next_status = self.NEXT.get(status)
        self.next_status = next_status
        panel = column(11)
        panel.padding = (dp(19), dp(18))
        paint(panel, ACCENT if next_status else WHITE, radius=20,
              stroke=None if next_status else LINE)
        panel.add_widget(words("YOUR NEXT ACTION", 11, PRIMARY, bold=True))
        if next_status is None:
            panel.add_widget(words("This request is resolved.", 21, INK, bold=True))
            panel.add_widget(words(
                "Only an accepted reopen request can return a resolved ticket to work.",
                14, MUTED,
            ))
        else:
            step = "Resume work" if status == "Reopened" else self.ACTION_LABELS[next_status]
            panel.add_widget(words(step, 22, INK, bold=True))
            panel.add_widget(words(f"{status}  →  {next_status}", 14, PRIMARY))
            self.status_button = action(
                f"{step}  →", self.request_status_update,
                fill=PRIMARY, ink=WHITE, height=54,
            )
            panel.add_widget(self.status_button)
            self.status_feedback = words(
                "Updates are saved to Status History and notify the student.",
                12, "#446653",
            )
            panel.add_widget(self.status_feedback)

        # Existing detail contains header, title and visual progress as its first
        # three widgets. Place this action straight after them, before comments.
        insert_position = max(0, len(self.content.children) - 3)
        self.content.add_widget(panel, index=insert_position)

    def request_status_update(self, _button):
        if self.ticket_id is None or self.next_status is None or self.status_button is None:
            return
        self.status_button.disabled = True
        if self.status_feedback:
            self.status_feedback.text = "Saving status update..."
        self.client.update_staff_status(self.ticket_id, self.next_status)

    def show_status_error(self, message):
        if self.status_feedback is not None:
            self.status_feedback.text = message
            self.status_feedback.color = color(ERROR)
        if self.status_button is not None:
            self.status_button.disabled = False


class AdminDashboard(Screen):
    """Campus-wide analytics plus server-side filtered complaints."""

    STATUSES = ("All statuses", "Open", "In Progress", "Resolved", "Reopened")
    ALL_CATEGORY = "All categories"
    AGE_ALL = "Any age"
    AGE_OVERDUE = "Over 7 days (unresolved)"

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.rows = []
        self.staff = []
        self.category_ids = {}
        self.page_number = 1
        self._suppress_filters = False
        self.scroller, body = page(self, 1050)
        body.add_widget(brand(client.sign_out))

        # Dispatch is the Admin's primary task; keep this heading short on phones.
        hero = column(12)
        hero.padding = (dp(23), dp(22))
        paint(hero, HERO, radius=23)
        heading = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        mark = AnchorLayout(size_hint_x=None, width=dp(44))
        mark.add_widget(FixlineGlyph("route", color=ACCENT,
                                      size_hint=(None, None), size=(dp(39), dp(39))))
        heading.add_widget(mark)
        name = column(3)
        name.add_widget(words("ADMIN  /  DISPATCH DESK", 12, ACCENT, bold=True))
        name.add_widget(words("Keep the campus moving.", 22, WHITE, bold=True))
        heading.add_widget(name)
        hero.add_widget(heading)
        hero.add_widget(words("Find requests without an owner, then send each fix to the right staff member.",
                              14, "#D7E8DD"))
        body.add_widget(hero)

        # The first actionable panel is grounded in the 20 currently fetched rows.
        attention = column(9)
        attention.padding = (dp(16), dp(16))
        paint(attention, "#E8F3DB", radius=18)
        quick_head = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        icon = AnchorLayout(size_hint_x=None, width=dp(44))
        glyph_panel = AnchorLayout(size_hint=(None, None), size=(dp(43), dp(43)))
        paint(glyph_panel, ACCENT, radius=13)
        glyph_panel.add_widget(FixlineGlyph("route", size_hint=(None, None),
                                            size=(dp(26), dp(26)), color=PRIMARY))
        icon.add_widget(glyph_panel)
        quick_head.add_widget(icon)
        summary = column(3)
        summary.add_widget(words("READY FOR DISPATCH", 11, "#46644F", bold=True))
        self.unassigned_label = words("Loading requests...", 17, INK, bold=True)
        summary.add_widget(self.unassigned_label)
        quick_head.add_widget(summary)
        attention.add_widget(quick_head)
        attention.add_widget(words(
            "Unassigned tickets from the current results page appear first below.",
            12, "#50685A",
        ))
        body.add_widget(attention)

        # Live statistics are campus-wide (GET /api/stats/basic).
        summary_title = column(5)
        summary_title.add_widget(words("Campus at a glance", 21, INK, bold=True))
        self.stats_feedback = words("Loading live campus totals...", 12, MUTED)
        summary_title.add_widget(self.stats_feedback)
        body.add_widget(summary_title)

        self.stats_grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None,
                                     row_default_height=dp(94), row_force_default=True)
        self.stats_values = {}
        stat_specs = (
            ("All requests", "total", "#FFFFFF", PRIMARY),
            ("Unresolved", "unresolved", "#FFF1CE", "#72501C"),
            ("Older than 7 days", "overdue", "#E0EFE8", "#205840"),
        )
        for label, key, bg, tint in stat_specs:
            metric = column(5)
            metric.padding = (dp(15), dp(12))
            metric.height = dp(94)
            metric.size_hint_y = None
            paint(metric, bg, radius=16, stroke=LINE)
            metric.add_widget(words(label, 12, MUTED, bold=True))
            value = words("—", 26, tint, bold=True)
            metric.add_widget(value)
            self.stats_grid.add_widget(metric)
            self.stats_values[key] = value
        body.add_widget(self.stats_grid)

        def resize_metrics(_widget, width):
            cols = 3 if width >= dp(610) else 2
            self.stats_grid.cols = cols
            rows = (len(stat_specs) + cols - 1) // cols
            self.stats_grid.height = dp(rows * 94 + (rows - 1) * 10)

        self.stats_grid.bind(width=resize_metrics)
        resize_metrics(None, 0)

        self.overdue_label = words("Unresolved over 7 days: —", 13, MUTED, bold=True)
        self.status_summary = words("Status breakdown: loading...", 13, MUTED)
        self.category_summary = words("Category breakdown: loading...", 13, MUTED)
        body.add_widget(self.status_summary)
        body.add_widget(self.category_summary)

        shortcuts = GridLayout(cols=2, spacing=dp(9), size_hint_y=None,
                               row_default_height=dp(49), row_force_default=True,
                               height=dp(49))
        shortcuts.add_widget(action("View overdue", lambda _btn: self.show_overdue(),
                                    fill=WHITE, ink=PRIMARY, height=49))
        shortcuts.add_widget(action("Review reopen requests", client.open_reopen_review,
                                    fill=WHITE, ink=PRIMARY, height=49))
        body.add_widget(shortcuts)

        self.notice = words("", 14, "#1C6243", bold=True)
        body.add_widget(self.notice)
        filter_heading = column(5)
        filter_heading.add_widget(words("Find a request", 21, INK, bold=True))
        filter_heading.add_widget(words(
            "Filter by category, progress or age. Select a ticket to assign staff.",
            13, MUTED,
        ))
        body.add_widget(filter_heading)
        controls = GridLayout(cols=2, spacing=dp(9), size_hint_y=None,
                              row_default_height=dp(48), row_force_default=True)
        self.category_filter = self.make_spinner(self.ALL_CATEGORY, (self.ALL_CATEGORY,))
        self.status_filter = self.make_spinner(self.STATUSES[0], self.STATUSES)
        self.age_filter = self.make_spinner(self.AGE_ALL, (self.AGE_ALL, self.AGE_OVERDUE))
        controls.add_widget(self.category_filter)
        controls.add_widget(self.status_filter)
        controls.add_widget(self.age_filter)
        controls.add_widget(action("Clear filters", self.clear_filters,
                                   fill=WHITE, ink=PRIMARY, height=48))

        def resize_filters(_widget, width):
            cols = 4 if width >= dp(760) else 2
            controls.cols = cols
            controls.height = dp(48 if cols == 4 else 105)
        controls.bind(width=resize_filters)
        resize_filters(None, 0)
        body.add_widget(controls)
        for field in (self.category_filter, self.status_filter, self.age_filter):
            field.bind(text=self.filters_changed)

        listbar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.count = words("", 13, MUTED)
        listbar.add_widget(self.count)
        listbar.add_widget(action("Refresh", lambda _btn: client.refresh_admin(),
                                   fill=WHITE, ink=PRIMARY, width=94, height=44))
        body.add_widget(listbar)

        self.tickets = column(12)
        body.add_widget(self.tickets)

        pager = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        self.prev = action("Previous", lambda _btn: client.load_admin_complaints(self.page_number - 1),
                           fill=WHITE, ink=PRIMARY, width=110, height=46)
        self.page_label = Label(text="Page 1", font_size=sp(14), color=color(MUTED))
        self.next = action("Next", lambda _btn: client.load_admin_complaints(self.page_number + 1),
                           fill=WHITE, ink=PRIMARY, width=90, height=46)
        pager.add_widget(self.prev)
        pager.add_widget(self.page_label)
        pager.add_widget(self.next)
        body.add_widget(pager)
        body.add_widget(words(
            "Up to 20 tickets per page. Only the statistics above represent the whole campus.",
            12, MUTED,
        ))
        self.show_message("Sign in as Admin to see campus requests.")
        self.update_pager()

    @staticmethod
    def make_spinner(title, options):
        widget = Spinner(
            text=title, values=options, option_cls=CategoryOption,
            font_size=sp(13), color=color(INK),
            background_normal="", background_down="", background_color=(0, 0, 0, 0),
        )
        paint(widget, WHITE, radius=11, stroke=LINE)
        return widget

    def set_stats(self, stats):
        self.stats_values["total"].text = str(stats.get("total", 0))
        self.stats_values["unresolved"].text = str(stats.get("unresolved", 0))
        overdue = stats.get("unresolved_over_7_days", 0)
        self.stats_values["overdue"].text = str(overdue)
        self.overdue_label.text = f"Unresolved over 7 days: {overdue}"
        status = stats.get("by_status", {})
        parts = [f"{name}: {status.get(name, 0)}" for name in
                 ("Open", "In Progress", "Resolved", "Reopened")]
        self.status_summary.text = "Progress  ·  " + "  |  ".join(parts)
        categories = [f"{item['name']}: {item['count']}" for item in
                      stats.get("by_category", [])]
        self.category_summary.text = (
            "By issue  ·  " + "  |  ".join(categories) if categories
            else "By issue  ·  No categories"
        )
        self.stats_feedback.text = "Live campus totals from PostgreSQL"
        self.stats_feedback.color = color(MUTED)

    def stats_error(self):
        self.stats_feedback.text = "Could not refresh campus statistics. Use Refresh to retry."
        self.stats_feedback.color = color(ERROR)

    def set_categories(self, categories):
        current = self.category_filter.text
        self.category_ids = {item["name"]: item["id"] for item in categories}
        opts = (self.ALL_CATEGORY, *self.category_ids.keys())
        self._suppress_filters = True
        self.category_filter.values = opts
        if current not in opts:
            self.category_filter.text = self.ALL_CATEGORY
        self._suppress_filters = False

    def active_filters(self):
        args = {}
        cat_id = self.category_ids.get(self.category_filter.text)
        if cat_id is not None:
            args["category_id"] = cat_id
        if self.status_filter.text != self.STATUSES[0]:
            args["status"] = self.status_filter.text
        if self.age_filter.text == self.AGE_OVERDUE:
            args["older_than_7_days"] = "true"
        return args

    def filters_changed(self, *_):
        if self._suppress_filters:
            return
        if (self.client.user and self.client.user.get("role") == "Admin"
                and self.client.screens.current == "admin_dashboard"):
            self.client.load_admin_complaints(1)

    def clear_filters(self, _button):
        self._suppress_filters = True
        self.category_filter.text = self.ALL_CATEGORY
        self.status_filter.text = self.STATUSES[0]
        self.age_filter.text = self.AGE_ALL
        self._suppress_filters = False
        self.filters_changed()

    def show_overdue(self):
        self._suppress_filters = True
        self.category_filter.text = self.ALL_CATEGORY
        self.status_filter.text = self.STATUSES[0]
        self.age_filter.text = self.AGE_OVERDUE
        self._suppress_filters = False
        self.filters_changed()

    def update_pager(self):
        self.page_label.text = f"Page {self.page_number}"
        self.prev.disabled = self.page_number <= 1
        self.next.disabled = len(self.rows) < 20

    def clear(self):
        self.rows = []
        self.staff = []
        self.category_ids = {}
        self.page_number = 1
        self._suppress_filters = True
        self.category_filter.text = self.ALL_CATEGORY
        self.category_filter.values = (self.ALL_CATEGORY,)
        self.status_filter.text = self.STATUSES[0]
        self.age_filter.text = self.AGE_ALL
        self._suppress_filters = False
        self.count.text = ""
        self.notice.text = ""
        self.unassigned_label.text = "Loading requests..."
        for field in self.stats_values.values():
            field.text = "—"
        self.overdue_label.text = "Unresolved over 7 days: —"
        self.status_summary.text = "Status breakdown: loading..."
        self.category_summary.text = "Category breakdown: loading..."
        self.stats_feedback.text = "Loading campus totals..."
        self.stats_feedback.color = color(MUTED)
        self.show_message("Sign in as Admin to see campus requests.")
        self.update_pager()

    def show_message(self, message):
        self.tickets.clear_widgets()
        self.tickets.add_widget(status_panel(message, "route"))

    def set_staff(self, staff):
        self.staff = list(staff)
        self.render_rows()

    def set_rows(self, rows, page_number):
        self.rows = list(rows)
        self.page_number = page_number
        self.render_rows()
        self.update_pager()

    def render_rows(self):
        self.count.text = f"{len(self.rows)} ticket(s) on page {self.page_number}"
        self.tickets.clear_widgets()
        unassigned = [record for record in self.rows if record.get("assigned_to") is None]
        others = [record for record in self.rows if record.get("assigned_to") is not None]
        self.unassigned_label.text = (
            f"{len(unassigned)} waiting for an owner on this page" if self.rows
            else "No tickets on this page"
        )
        if not self.rows:
            self.show_message("No complaints match these filters." if self.page_number == 1
                              else "No more results. Use Previous to go back.")
            self.update_pager()
            return

        staff_names = {u["id"]: u["name"] for u in self.staff}
        palette = {name: (glyph, shade) for name, glyph, _hint, shade in FIXLINE_CATEGORIES}

        def group(label, caption, tickets):
            if not tickets:
                return
            title = column(3)
            title.add_widget(words(label, 17, INK, bold=True))
            title.add_widget(words(caption, 12, MUTED))
            self.tickets.add_widget(title)
            for item in tickets:
                category = str(item.get("category_name") or "Other")
                glyph, tile_fill = palette.get(category, ("other", NEUTRAL))
                status = str(item.get("status") or "Open")
                fill, tint = STATUS_COLORS.get(status, (NEUTRAL, MUTED))
                owner_id = item.get("assigned_to")
                owner_name = staff_names.get(owner_id, f"Staff #{owner_id}") if owner_id is not None else "Needs assignment"
                card = TicketRow(
                    orientation="vertical", size_hint_y=None,
                    padding=(dp(15), dp(14)), spacing=dp(9),
                )
                card.bind(minimum_height=card.setter("height"))
                card_fill = "#FFFFFF" if owner_id is not None else "#FFFDF5"
                shade = paint(card, card_fill, radius=18, stroke="#E8E5D6" if owner_id is None else LINE)
                card.bind(
                    state=lambda _w, state, sh=shade, base=card_fill: setattr(
                        sh, "rgba", color(PALE if state == "down" else base)
                    ),
                    on_release=lambda _w, selected=dict(item): self.client.open_admin_assign(selected),
                )

                heading = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
                icon_bg = AnchorLayout(size_hint_x=None, width=dp(44))
                icon_frame = AnchorLayout(size_hint=(None, None), size=(dp(43), dp(43)))
                paint(icon_frame, tile_fill, radius=12)
                icon_frame.add_widget(FixlineGlyph(
                    glyph, color=INK, size_hint=(None, None), size=(dp(27), dp(27))
                ))
                icon_bg.add_widget(icon_frame)
                heading.add_widget(icon_bg)
                meta = column(3)
                meta.add_widget(words(f"REQUEST #{item['id']}", 11, MUTED, bold=True))
                meta.add_widget(words(category, 15, INK, bold=True))
                heading.add_widget(meta)
                # A persistent direction label makes the whole card's action clear.
                hint = AnchorLayout(anchor_x="right", size_hint_x=None, width=dp(90))
                hint.add_widget(words(
                    "ASSIGN  ›" if owner_id is None else "REASSIGN  ›",
                    12, PRIMARY, bold=True,
                ))
                heading.add_widget(hint)
                card.add_widget(heading)
                card.add_widget(words(str(item.get("title") or "Untitled request"),
                                      18, INK, bold=True))
                footer = BoxLayout(size_hint_y=None, height=dp(31), spacing=dp(9))
                footer.add_widget(pill(status, 112, fill, tint, 28))
                owner = words(owner_name, 12, "#925E21" if owner_id is None else MUTED)
                footer.add_widget(owner)
                card.add_widget(footer)
                self.tickets.add_widget(card)

        group("Needs an owner", "Unassigned requests from this results page.", unassigned)
        group("Already in motion", "Assigned requests you can reassign if needed.", others)



class AdminAssignScreen(Screen):
    """Choose a real Staff user from the backend's dropdown, never type an ID."""
    PLACEHOLDER = "Choose a staff member"

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.record = None
        self.staff_ids = {}
        self.busy = False
        self.scroller, body = page(self, 740)
        body.add_widget(brand(client.sign_out))
        body.add_widget(action("‹  Back to dispatch", client.back_to_admin_dashboard,
                               fill=WHITE, ink=PRIMARY, width=210, height=44))
        hero = column(8)
        hero.padding = (dp(22), dp(19))
        paint(hero, HERO, radius=20)
        hero.add_widget(words("DISPATCH A FIX", 12, ACCENT, bold=True))
        hero.add_widget(words("Choose who's on it.", 24, WHITE, bold=True))
        hero.add_widget(words("One request, one clear owner. You can reassign when needed.",
                              13, "#D7E8DD"))
        body.add_widget(hero)
        self.content = column(12)
        body.add_widget(self.content)
        self.form = column(13)
        self.form.padding = (dp(19), dp(19))
        paint(self.form, WHITE, radius=18, stroke=LINE)
        self.content.add_widget(self.form)
        self.staff_spinner = Spinner(
            text=self.PLACEHOLDER, values=[], option_cls=CategoryOption,
            color=color(INK), font_size=sp(14), size_hint_y=None, height=dp(52),
            background_normal="", background_down="", background_color=(0, 0, 0, 0),
        )
        paint(self.staff_spinner, BG, radius=11, stroke=LINE)
        self.save = action("Confirm assignment", self.assign, height=54)
        self.feedback = words("", 13, MUTED)
        self.show_record(None, [])

    def clear(self):
        self.record = None
        self.staff_ids = {}
        self.busy = False
        self.show_record(None, [])

    def show_record(self, record, staff):
        self.record = record
        self.busy = False
        self.form.clear_widgets()
        self.staff_ids = {f"{user['name']}  (#{user['id']})": user["id"] for user in staff}
        self.staff_spinner.text = self.PLACEHOLDER
        self.staff_spinner.values = list(self.staff_ids)
        self.staff_spinner.disabled = not self.staff_ids
        self.save.disabled = not self.staff_ids
        if record is None:
            self.form.add_widget(words("Select a request from the dispatch desk.", 15, MUTED))
            return
        category = str(record.get("category_name") or "Other")
        palette = {name: (glyph, bg) for name, glyph, _subtitle, bg in FIXLINE_CATEGORIES}
        glyph, bg = palette.get(category, ("other", PALE))
        header = BoxLayout(size_hint_y=None, height=dp(53), spacing=dp(12))
        mark = AnchorLayout(size_hint_x=None, width=dp(53))
        icon_bg = AnchorLayout(size_hint=(None, None), size=(dp(51), dp(51)))
        paint(icon_bg, bg, radius=13)
        icon_bg.add_widget(FixlineGlyph(
            glyph, color=INK, size_hint=(None, None), size=(dp(31), dp(31))))
        mark.add_widget(icon_bg)
        header.add_widget(mark)
        description = column(3)
        description.add_widget(words(f"REQUEST #{record['id']}", 11, MUTED, bold=True))
        description.add_widget(words(category, 17, INK, bold=True))
        header.add_widget(description)
        self.form.add_widget(header)
        self.form.add_widget(words(str(record.get("title") or "Untitled request"),
                                   22, INK, bold=True))
        status = str(record.get("status") or "Open")
        fill, tint = STATUS_COLORS.get(status, (NEUTRAL, MUTED))
        badge_row = BoxLayout(size_hint_y=None, height=dp(31))
        badge_row.add_widget(pill(status, 112, fill, tint, 28))
        badge_row.add_widget(Widget())
        self.form.add_widget(badge_row)
        current = record.get("assigned_to")
        current_name = next((user["name"] for user in staff if user["id"] == current), None)
        owner = (f"{current_name} (#{current})" if current_name else
                 f"Staff #{current}" if current is not None else "Nobody yet — needs assignment")
        self.form.add_widget(words("CURRENT OWNER", 12, MUTED, bold=True))
        self.form.add_widget(words(owner, 15, INK))
        separator = Widget(size_hint_y=None, height=dp(1))
        paint(separator, LINE, radius=0)
        self.form.add_widget(separator)
        self.form.add_widget(words("Assign to staff", 17, INK, bold=True))
        self.form.add_widget(words("Select the person responsible for this request.", 13, MUTED))
        self.form.add_widget(self.staff_spinner)
        self.form.add_widget(self.save)
        self.feedback = words("", 13, MUTED)
        self.form.add_widget(self.feedback)
        if not self.staff_ids:
            self.feedback.text = "Loading staff options, or no Staff accounts exist."
            self.form.add_widget(action(
                "Reload staff list", lambda _btn: self.client.load_admin_staff(),
                fill=WHITE, ink=PRIMARY,
            ))
        self.scroller.scroll_y = 1

    def assign(self, _button):
        if not self.record or self.busy:
            return
        staff_id = self.staff_ids.get(self.staff_spinner.text)
        if staff_id is None:
            self.feedback.text = "Please select a staff member from the dropdown."
            self.feedback.color = color(ERROR)
            return
        if staff_id == self.record.get("assigned_to"):
            self.feedback.text = "This ticket is already assigned to that staff member."
            self.feedback.color = color(ERROR)
            return
        self.busy = True
        self.save.disabled = True
        self.staff_spinner.disabled = True
        self.feedback.color = color(MUTED)
        self.feedback.text = "Saving assignment..."
        self.client.submit_admin_assignment(self.record["id"], staff_id)

    def show_error(self, message):
        self.busy = False
        self.save.disabled = not self.staff_ids
        self.staff_spinner.disabled = not self.staff_ids
        self.feedback.color = color(ERROR)
        self.feedback.text = message


class ReopenReviewScreen(Screen):
    """Pending review queue for the signed-in Staff or Admin user."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.busy = False
        self.scroller, body = page(self, 850)
        body.add_widget(action("Back", client.close_reopen_review,
                               fill=WHITE, ink=PRIMARY, width=120, height=44))
        hero = column(8)
        hero.padding = (dp(22), dp(22))
        paint(hero, HERO, radius=22)
        hero.add_widget(words("REVIEW WORKSPACE", 11, ACCENT, bold=True))
        hero.add_widget(words("Reopen requests", 29, WHITE, bold=True))
        hero.add_widget(words("Read each reason before accepting or declining.", 14, "#D7E8DD"))
        body.add_widget(hero)

        toolbar = BoxLayout(size_hint_y=None, height=dp(46))
        self.summary = words("", 14, MUTED)
        toolbar.add_widget(self.summary)
        toolbar.add_widget(action("Refresh", lambda _btn: client.load_pending_reopen(),
                                  fill=WHITE, ink=PRIMARY, height=44, width=96))
        body.add_widget(toolbar)
        self.feed = column(12)
        body.add_widget(self.feed)
        self.show_message("Loading pending requests...")

    def clear(self):
        self.busy = False
        self.summary.text = ""
        self.show_message("Loading pending requests...")

    def show_message(self, message):
        self.feed.clear_widgets()
        self.feed.add_widget(status_panel(message, "route"))

    def show_requests(self, records):
        self.feed.clear_widgets()
        self.summary.text = f"{len(records)} pending"
        if not records:
            self.feed.add_widget(status_panel(
                "No pending reopen requests. New requests will appear here for review.", "check"
            ))
            return
        for record in records:
            card = column(12)
            card.padding = (dp(17), dp(17))
            paint(card, WHITE, radius=19, stroke=LINE)
            card.add_widget(words(f"Complaint #{record['complaint_id']}",
                                  19, INK, bold=True))
            card.add_widget(words(f"Requested: {readable_timestamp(record.get('created_at'))}",
                                  13, MUTED))
            card.add_widget(words(str(record.get("reason") or ""), 15, INK))
            card.add_widget(words("Accept reopens the complaint; decline keeps it Resolved.",
                                  13, MUTED))
            controls = BoxLayout(spacing=dp(9), size_hint_y=None, height=dp(47))
            controls.add_widget(action(
                "Accept", lambda _btn, item=record: self.confirm(item, "Accepted"),
                fill=PRIMARY, ink=WHITE, height=47,
            ))
            controls.add_widget(action(
                "Decline", lambda _btn, item=record: self.confirm(item, "Declined"),
                fill=NEUTRAL, ink=INK, height=47,
            ))
            card.add_widget(controls)
            self.feed.add_widget(card)
        self.scroller.scroll_y = 1

    def confirm(self, record, decision):
        if self.busy or not isinstance(record.get("id"), int):
            return
        dialog = Popup(title="Confirm decision", size_hint=(.90, None),
                       height=dp(245), auto_dismiss=False)
        area = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(15))
        note = words(
            f"{decision} reopen request #{record['id']} for Complaint #{record['complaint_id']}?",
            15, INK,
        )
        area.add_widget(note)
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        buttons.add_widget(action("Cancel", lambda _btn: dialog.dismiss(),
                                  fill=NEUTRAL, ink=INK, height=47))
        def submit(_btn):
            dialog.dismiss()
            self.busy = True
            self.summary.text = "Saving decision..."
            self.client.decide_reopen_request(record["id"], decision)
        buttons.add_widget(action("Confirm", submit, height=47))
        area.add_widget(buttons)
        dialog.content = area
        dialog.open()


class CampusFixApp(App):
    def build(self):
        self.title = "CampusFix"
        Window.clearcolor = color(BG)
        self.token = None
        self.user = None
        self.session_version = 0
        self.list_loading = False
        self.list_version = 0
        self.detail_version = 0
        self.detail_origin = "dashboard"
        self.staff_list_version = 0
        self.staff_detail_version = 0
        self.admin_list_version = 0
        self.admin_staff_version = 0
        self.admin_stats_version = 0
        self.admin_categories_version = 0
        self.admin_assign_version = 0
        self.notification_list_version = 0
        self.notification_count_version = 0
        self.reopen_history_version = 0
        self.reopen_review_version = 0
        self.reopen_review_origin = "staff_dashboard"
        self.admin_page = 1
        self.admin_staff = []
        self.screens = ScreenManager(transition=SlideTransition(duration=.18))
        self.login = LoginScreen(self, name="login")
        self.register_screen = RegisterScreen(self, name="register")
        self.dashboard = Dashboard(
            self.open_form, self.sign_out, self.load_complaints,
            self.open_detail, self.open_all, self.open_notifications,
            name="dashboard"
        )
        self.notifications_screen = NotificationsScreen(self, name="notifications")
        self.my_complaints = MyComplaintsScreen(
            self.open_dashboard, self.load_complaints, self.open_detail, name="my_complaints"
        )
        self.form = ComplaintForm(self, self.open_dashboard, name="new_complaint")
        self.detail = ComplaintDetailScreen(self.close_detail, self.open_detail, client=self, name="complaint_detail")
        self.staff_dashboard = StaffDashboard(self, name="staff_dashboard")
        self.staff_detail = StaffDetailScreen(self, name="staff_detail")
        self.admin_dashboard = AdminDashboard(self, name="admin_dashboard")
        self.admin_assign = AdminAssignScreen(self, name="admin_assign")
        self.reopen_review = ReopenReviewScreen(self, name="reopen_review")
        self.screens.add_widget(self.login)
        self.screens.add_widget(self.register_screen)
        self.screens.add_widget(self.dashboard)
        self.screens.add_widget(self.notifications_screen)
        self.screens.add_widget(self.my_complaints)
        self.screens.add_widget(self.form)
        self.screens.add_widget(self.detail)
        self.screens.add_widget(self.staff_dashboard)
        self.screens.add_widget(self.staff_detail)
        self.screens.add_widget(self.admin_dashboard)
        self.screens.add_widget(self.admin_assign)
        self.screens.add_widget(self.reopen_review)
        return self.screens

    def call(self, method, path, expected, done, *, body=None, protected=False):
        version = self.session_version
        if protected and not self.token:
            self.sign_out(None, expired=True)
            return

        def deliver(data, error):
            if version != self.session_version:
                return
            if protected and error == 401:
                self.sign_out(None, expired=True)
                return
            done(data, error)

        send_json(method, path, expected, deliver, body=body, token=self.token if protected else None)

    def navigate(self, screen, direction):
        self.screens.transition.direction = direction
        self.screens.current = screen

    def open_registration(self, _button):
        self.login.password.text = ""
        self.register_screen.show_message("New accounts are created with the Student role.")
        self.navigate("register", "left")

    def back_to_login(self, _button):
        if self.register_screen.busy:
            return
        self.register_screen.password.text = ""
        self.register_screen.confirm_password.text = ""
        self.navigate("login", "right")

    def registration_complete(self, email):
        self.login.email.text = email
        self.login.password.text = ""
        self.login.show_message("Account created! Sign in with your new password.")
        self.navigate("login", "right")

    def signed_in(self, token, user):
        self.session_version += 1
        self.token = token
        self.user = user
        self.dashboard.show_notice("")
        role = user.get("role")
        if role == "Staff":
            self.open_staff_queue(None)
        elif role == "Admin":
            self.open_admin_dashboard(None)
        elif role == "Student":
            self.open_dashboard(None)
        else:
            self.sign_out(None)
            self.login.show_message("This account has an unsupported role.", error=True)

    def sign_out(self, _button, *, expired=False):
        self.session_version += 1
        self.token = self.user = None
        self.list_loading = False
        self.dashboard.show_notice("")
        self.dashboard.set_unread_count(None)
        self.notification_list_version += 1
        self.notification_count_version += 1
        self.reopen_history_version += 1
        self.reopen_review_version += 1
        self.reopen_review.clear()
        self.notifications_screen.clear()
        self.dashboard.tickets.clear_widgets()
        self.my_complaints.clear()
        self.form.reset_form()
        self.detail_version += 1
        self.detail.clear()
        self.staff_list_version += 1
        self.staff_detail_version += 1
        self.staff_dashboard.clear()
        self.staff_detail.clear()
        self.admin_list_version += 1
        self.admin_staff_version += 1
        self.admin_stats_version += 1
        self.admin_categories_version += 1
        self.admin_assign_version += 1
        self.admin_page = 1
        self.admin_staff = []
        self.admin_dashboard.clear()
        self.admin_assign.clear()
        self.login.set_busy(False)
        self.login.password.text = ""
        if not expired:
            self.login.email.text = ""
        self.login.show_message(
            "Your session expired. Sign in again." if expired else "Signed out of CampusFix."
        )
        self.navigate("login", "right")


    def open_admin_dashboard(self, _button):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        self.navigate("admin_dashboard", "right")
        self.refresh_admin()

    def refresh_admin(self):
        self.load_admin_staff()
        self.load_admin_categories()
        self.load_admin_stats()
        self.load_admin_complaints(self.admin_page)

    def load_admin_stats(self):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        self.admin_stats_version += 1
        version = self.admin_stats_version

        def finish(data, error):
            if version != self.admin_stats_version:
                return
            valid = (isinstance(data, dict) and
                     all(isinstance(data.get(k), int) for k in
                         ("total", "unresolved", "unresolved_over_7_days")) and
                     isinstance(data.get("by_status"), dict) and
                     isinstance(data.get("by_category"), list))
            if error is not None or not valid:
                self.admin_dashboard.stats_error()
            else:
                self.admin_dashboard.set_stats(data)

        self.call("GET", "/api/stats/basic", 200, finish, protected=True)

    def load_admin_categories(self):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        self.admin_categories_version += 1
        version = self.admin_categories_version

        def finish(data, error):
            if version != self.admin_categories_version:
                return
            if error is not None or not isinstance(data, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("id"), int)
                or not isinstance(item.get("name"), str) for item in data
            ):
                self.admin_dashboard.notice.text = "Could not load categories. Tap Refresh to retry."
                return
            self.admin_dashboard.set_categories(data)

        self.call("GET", "/api/categories", 200, finish, protected=True)

    def load_admin_staff(self):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        self.admin_staff_version += 1
        version = self.admin_staff_version

        def finish(data, error):
            if version != self.admin_staff_version:
                return
            if error is not None or not isinstance(data, list) or any(
                not isinstance(user, dict) or not all(
                    field in user for field in ("id", "name")
                ) for user in data
            ):
                if self.screens.current == "admin_assign":
                    self.admin_assign.show_error("Could not load staff. Go back and try again.")
                return
            self.admin_staff = data
            self.admin_dashboard.set_staff(data)
            if self.screens.current == "admin_assign" and self.admin_assign.record:
                self.admin_assign.show_record(self.admin_assign.record, data)

        self.call("GET", "/api/admin/staff", 200, finish, protected=True)

    def load_admin_complaints(self, page_number=None):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        page_number = self.admin_page if page_number is None else page_number
        if not isinstance(page_number, int) or page_number < 1:
            return
        self.admin_list_version += 1
        version = self.admin_list_version
        self.admin_dashboard.show_message("Loading campus complaints...")
        self.admin_dashboard.prev.disabled = True
        self.admin_dashboard.next.disabled = True

        def finish(data, error):
            if version != self.admin_list_version:
                return
            if error is not None or not isinstance(data, list) or any(
                not isinstance(item, dict) or not all(
                    key in item for key in
                    ("id", "title", "status", "category_name", "assigned_to")
                ) for item in data
            ):
                self.admin_dashboard.show_message("Could not load complaints. Tap Refresh to retry.")
                self.admin_dashboard.update_pager()
                return
            self.admin_page = page_number
            self.admin_dashboard.set_rows(data, page_number)

        query_args = {"page": page_number, **self.admin_dashboard.active_filters()}
        path = "/api/admin/complaints/search?" + urlencode(query_args)
        self.call("GET", path, 200, finish, protected=True)

    def open_admin_assign(self, complaint):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        if not isinstance(complaint, dict) or not isinstance(complaint.get("id"), int):
            return
        self.admin_assign_version += 1
        self.admin_assign.show_record(complaint, self.admin_staff)
        self.navigate("admin_assign", "left")
        if not self.admin_staff:
            self.load_admin_staff()

    def back_to_admin_dashboard(self, _button):
        self.admin_assign_version += 1
        self.admin_assign.clear()
        self.navigate("admin_dashboard", "right")

    def submit_admin_assignment(self, complaint_id, staff_id):
        if not self.token or not self.user or self.user.get("role") != "Admin":
            return
        version = self.admin_assign_version

        def finish(data, error):
            if version != self.admin_assign_version or self.screens.current != "admin_assign":
                return
            if error == 409:
                self.admin_assign.show_error("This assignment may have changed. Refresh and try again.")
            elif error in (403, 404, 422):
                self.admin_assign.show_error("Could not assign. Check the ticket and selected staff member.")
            elif error is not None or not isinstance(data, dict) or (
                data.get("complaint_id") != complaint_id or data.get("staff_id") != staff_id
            ):
                self.admin_assign.show_error("Assignment not confirmed. Check the list before retrying.")
            else:
                selected_name = next(
                    (u["name"] for u in self.admin_staff if u["id"] == staff_id),
                    f"Staff #{staff_id}",
                )
                self.back_to_admin_dashboard(None)
                self.admin_dashboard.notice.text = f"Complaint #{complaint_id} assigned to {selected_name}."
                self.load_admin_complaints(self.admin_page)

        self.call(
            "PUT", f"/api/admin/complaints/{complaint_id}/assignment", 200, finish,
            body={"staff_id": staff_id}, protected=True,
        )

    def open_staff_queue(self, _button):
        if not self.token or not self.user or self.user.get("role") != "Staff":
            return
        self.navigate("staff_dashboard", "right")
        self.load_staff_queue()

    def back_to_staff_queue(self, _button):
        self.staff_detail_version += 1
        self.staff_detail.clear()
        self.open_staff_queue(None)

    def load_staff_queue(self):
        if not self.token or not self.user or self.user.get("role") != "Staff":
            return
        self.staff_list_version += 1
        version = self.staff_list_version
        self.staff_dashboard.show_message("Loading assigned requests...")
        unresolved = "true" if self.staff_dashboard.filter.text == "Unresolved" else "false"

        def finish(data, error):
            if version != self.staff_list_version:
                return
            if error == 403:
                self.staff_dashboard.show_message("Only staff accounts can view this queue.")
            elif error is not None or not isinstance(data, list) or any(
                not isinstance(item, dict) or not all(
                    key in item for key in ("id", "title", "status", "category_name")
                ) for item in data
            ):
                self.staff_dashboard.show_message("Could not load assigned requests. Tap Refresh to retry.")
            else:
                self.staff_dashboard.show_complaints(data)

        self.call("GET", f"/api/staff/complaints?unresolved={unresolved}", 200, finish, protected=True)

    def open_staff_detail(self, ticket_id):
        if not self.token or not self.user or self.user.get("role") != "Staff":
            return
        if not isinstance(ticket_id, int) or ticket_id < 1:
            return
        self.staff_detail_version += 1
        version = self.staff_detail_version
        self.staff_detail.show_loading(ticket_id)
        self.navigate("staff_detail", "left")

        def finish(data, error):
            if version != self.staff_detail_version or self.screens.current != "staff_detail":
                return
            if error in (403, 404):
                self.staff_detail.show_error("This request is not assigned to your account.", allow_retry=False)
            elif error is not None or not isinstance(data, dict) or data.get("id") != ticket_id or any(
                not isinstance(data.get(key), str)
                for key in ("title", "category_name", "status", "location", "description")
            ):
                self.staff_detail.show_error("Could not load this ticket. Tap Try again to retry.")
            else:
                self.staff_detail.show_complaint(data)
                self.load_comments(ticket_id, "staff")

        self.call("GET", f"/api/staff/complaints/{ticket_id}", 200, finish, protected=True)

    def update_staff_status(self, ticket_id, new_status):
        if not self.token or not self.user or self.user.get("role") != "Staff":
            return
        version = self.staff_detail_version

        def finish(data, error):
            if (version != self.staff_detail_version or self.screens.current != "staff_detail"
                    or self.staff_detail.ticket_id != ticket_id):
                return
            if error == 409:
                self.staff_detail.show_status_error("Status was already changed. Go back and reopen the ticket.")
            elif error in (403, 404):
                self.staff_detail.show_status_error("This ticket is no longer assigned to you.")
            elif error is not None or not isinstance(data, dict) or data.get("new_status") != new_status:
                self.staff_detail.show_status_error("Could not confirm the update. Check the ticket before trying again.")
            else:
                # Reload fresh status and history; do not assume the UI already has them.
                self.open_staff_detail(ticket_id)

        self.call(
            "PUT", f"/api/staff/complaints/{ticket_id}/status", 200, finish,
            body={"new_status": new_status}, protected=True,
        )

    def active_comment_screen(self, ticket_id, role):
        """Return an active authorized detail screen or None."""
        expected_role = "Staff" if role == "staff" else "Student"
        screen_name = "staff_detail" if role == "staff" else "complaint_detail"
        if (not self.token or not self.user or self.user.get("role") != expected_role
                or self.screens.current != screen_name):
            return None
        screen = self.staff_detail if role == "staff" else self.detail
        if screen.ticket_id != ticket_id or screen.comment_feed is None:
            return None
        return screen

    def load_comments(self, ticket_id, role):
        screen = self.active_comment_screen(ticket_id, role)
        if screen is None:
            return
        screen.comment_version += 1
        version = screen.comment_version
        screen.comment_feed.clear_widgets()
        screen.comment_feed.add_widget(words("Loading replies...", 14, MUTED))

        def finish(data, error):
            current = self.active_comment_screen(ticket_id, role)
            if current is not screen or current.comment_version != version:
                return
            if error in (403, 404):
                current.show_comments_error("You no longer have access to these replies.")
            elif (error is not None or not isinstance(data, list)
                  or any(not isinstance(item, dict)
                         or not all(key in item for key in ("body", "author_name", "created_at"))
                         for item in data)):
                current.show_comments_error("Could not load replies. Check the connection and retry.")
            else:
                current.show_comments(data)

        self.call("GET", f"/api/complaints/{ticket_id}/comments", 200, finish,
                  protected=True)

    def post_comment(self, ticket_id, role, message):
        screen = self.active_comment_screen(ticket_id, role)
        if screen is None:
            return
        version = screen.comment_version

        def finish(data, error):
            current = self.active_comment_screen(ticket_id, role)
            if current is not screen or current.comment_version != version:
                return
            if current.comment_button is not None:
                current.comment_button.disabled = False
            if error in (403, 404):
                current.set_comment_notice("You cannot reply to this ticket.", error=True)
            elif error == 422:
                current.set_comment_notice("Reply must contain 1–2,000 characters.", error=True)
            elif (error is not None or not isinstance(data, dict)
                  or data.get("complaint_id") != ticket_id
                  or data.get("body") != message):
                current.set_comment_notice(
                    "Reply could not be confirmed. Refresh replies before retrying.", error=True
                )
            else:
                current.comment_entry.text = ""
                current.set_comment_notice("Reply sent successfully.")
                self.load_comments(ticket_id, role)

        self.call("POST", f"/api/complaints/{ticket_id}/comments", 201, finish,
                  body={"body": message}, protected=True)

    def load_notification_count(self):
        """Update the student badge on dashboard navigation; no background polling."""
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.notification_count_version += 1
        request_version = self.notification_count_version

        def received(data, error):
            if request_version != self.notification_count_version:
                return
            if error is None and isinstance(data, dict):
                self.dashboard.set_unread_count(data.get("unread_count"))
            else:
                self.dashboard.set_unread_count(None)

        self.call("GET", "/api/notifications/unread-count", 200, received, protected=True)

    def open_notifications(self, _button):
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.navigate("notifications", "left")
        self.load_notifications()
        self.load_notification_count()

    def load_notifications(self):
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.notification_list_version += 1
        request_version = self.notification_list_version
        self.notifications_screen.summary.text = ""
        self.notifications_screen.show_message("Loading notifications...")

        def received(data, error):
            if (request_version != self.notification_list_version
                    or self.screens.current != "notifications"):
                return
            if (error is not None or not isinstance(data, list)
                    or any(not isinstance(item, dict)
                           or not isinstance(item.get("id"), int)
                           or not isinstance(item.get("complaint_id"), int)
                           or item["complaint_id"] < 1 for item in data)):
                self.notifications_screen.show_message(
                    "Could not load notifications. Use Refresh to retry."
                )
            else:
                self.notifications_screen.show_notifications(data)

        self.call("GET", "/api/notifications", 200, received, protected=True)

    def open_notification(self, notification):
        """Mark notification read, then open that student's complaint."""
        if (not self.token or not self.user or self.user.get("role") != "Student"
                or self.screens.current != "notifications"):
            return
        ticket_id = notification.get("complaint_id")
        note_id = notification.get("id")
        if (not isinstance(ticket_id, int) or ticket_id < 1
                or not isinstance(note_id, int) or note_id < 1):
            self.notifications_screen.show_message("Invalid notification. Tap Refresh.")
            return

        def go_to_complaint():
            self.detail_origin = "notifications"
            self.open_detail(ticket_id)

        if notification.get("read_at") is not None:
            go_to_complaint()
            return

        self.notifications_screen.show_message("Opening complaint...")
        self.notification_list_version += 1

        def marked(data, error):
            if self.screens.current != "notifications":
                return
            if error is not None:
                self.notifications_screen.show_message(
                    "Unable to mark as read. Use Refresh to retry."
                )
                return
            self.load_notification_count()
            go_to_complaint()

        self.call("PUT", f"/api/notifications/{note_id}/read", 200,
                  marked, protected=True)


    def load_reopen_history(self, ticket_id):
        """Read archived reopen decisions for the current student ticket."""
        if (not self.token or not self.user or self.user.get("role") != "Student"
                or self.screens.current != "complaint_detail"
                or self.detail.ticket_id != ticket_id):
            return
        self.reopen_history_version += 1
        version = self.reopen_history_version
        detail_version = self.detail_version

        def finish(data, error):
            if (version != self.reopen_history_version or detail_version != self.detail_version
                    or self.screens.current != "complaint_detail"
                    or self.detail.ticket_id != ticket_id):
                return
            if (error is not None or not isinstance(data, list)
                    or any(not isinstance(item, dict) or not isinstance(item.get("id"), int)
                           or item.get("complaint_id") != ticket_id for item in data)):
                self.detail.show_reopen_error("Could not load reopen requests.")
            else:
                self.detail.show_reopen_requests(data)

        self.call("GET", f"/api/complaints/{ticket_id}/reopen-requests", 200,
                  finish, protected=True)

    def submit_reopen_request(self, ticket_id, reason):
        if (not self.token or not self.user or self.user.get("role") != "Student"
                or self.screens.current != "complaint_detail"
                or self.detail.ticket_id != ticket_id):
            return
        version = self.detail_version

        def finish(data, error):
            if (version != self.detail_version or self.screens.current != "complaint_detail"
                    or self.detail.ticket_id != ticket_id):
                return
            if error == 409:
                self.detail.set_reopen_notice("Already pending or no longer Resolved. Reload complaint.", error=True)
                self.load_reopen_history(ticket_id)
            elif error in (403, 404):
                self.detail.set_reopen_notice("This complaint is not available for your account.", error=True)
            elif error == 422:
                self.detail.set_reopen_notice("Please enter a valid reason (1–2,000 characters).", error=True)
                if self.detail.reopen_button:
                    self.detail.reopen_button.disabled = False
            elif (error is not None or not isinstance(data, dict)
                  or data.get("complaint_id") != ticket_id
                  or data.get("status") != "Pending"):
                self.detail.set_reopen_notice(
                    "Submission not confirmed. Refresh requests before retrying.", error=True
                )
            else:
                self.detail.set_reopen_notice("Reopen request sent for review.")
                if self.detail.reopen_editor:
                    self.detail.reopen_editor.text = ""
                self.load_reopen_history(ticket_id)

        self.call("POST", f"/api/complaints/{ticket_id}/reopen", 201,
                  finish, body={"reason": reason}, protected=True)

    def open_reopen_review(self, _button):
        if (not self.token or not self.user
                or self.user.get("role") not in ("Staff", "Admin")):
            return
        self.reopen_review_origin = (
            "admin_dashboard" if self.user["role"] == "Admin" else "staff_dashboard"
        )
        self.reopen_review.clear()
        self.navigate("reopen_review", "left")
        self.load_pending_reopen()

    def close_reopen_review(self, _button):
        self.reopen_review_version += 1
        self.reopen_review.clear()
        if self.reopen_review_origin == "admin_dashboard":
            self.open_admin_dashboard(None)
        else:
            self.open_staff_queue(None)

    def load_pending_reopen(self):
        if (not self.token or not self.user
                or self.user.get("role") not in ("Staff", "Admin")
                or self.screens.current != "reopen_review"):
            return
        self.reopen_review_version += 1
        version = self.reopen_review_version
        self.reopen_review.busy = False
        self.reopen_review.show_message("Loading pending requests...")

        def finish(data, error):
            if version != self.reopen_review_version or self.screens.current != "reopen_review":
                return
            if (error is not None or not isinstance(data, list)
                    or any(not isinstance(item, dict) or not isinstance(item.get("id"), int)
                           or not isinstance(item.get("complaint_id"), int)
                           or item.get("status") != "Pending" for item in data)):
                self.reopen_review.show_message("Couldn't load requests. Tap Refresh.")
            else:
                self.reopen_review.show_requests(data)

        self.call("GET", "/api/reopen/pending", 200, finish, protected=True)

    def decide_reopen_request(self, request_id, decision):
        if (not self.token or not self.user or self.user.get("role") not in ("Staff", "Admin")
                or self.screens.current != "reopen_review"
                or not self.reopen_review.busy):
            return
        version = self.reopen_review_version

        def finish(data, error):
            if version != self.reopen_review_version or self.screens.current != "reopen_review":
                return
            self.reopen_review.busy = False
            if error == 409:
                self.reopen_review.summary.text = "Already decided or complaint changed."
                self.load_pending_reopen()
            elif error in (403, 404):
                self.reopen_review.summary.text = "Not authorized or request unavailable."
                self.load_pending_reopen()
            elif (error is not None or not isinstance(data, dict)
                  or data.get("id") != request_id or data.get("status") != decision):
                self.reopen_review.summary.text = "Decision not confirmed. Refresh before retrying."
                self.load_pending_reopen()
            else:
                self.load_pending_reopen()
                self.reopen_review.summary.text = f"Request #{request_id}: {decision}."

        self.call("PUT", f"/api/reopen/{request_id}", 200, finish,
                  body={"decision": decision}, protected=True)

    def open_form(self, _button, category_name=None):
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.dashboard.show_notice("")
        self.form.prefill_category(category_name)
        self.navigate("new_complaint", "left")

    def open_dashboard(self, _button):
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.navigate("dashboard", "right")
        self.load_complaints()
        self.load_notification_count()

    def open_all(self, _button):
        if not self.token or not self.user or self.user.get("role") != "Student":
            return
        self.navigate("my_complaints", "left")
        self.load_complaints(force=True)

    def open_detail(self, ticket_id):
        if (not self.token or not self.user or self.user.get("role") != "Student"
                or not isinstance(ticket_id, int) or ticket_id < 1):
            return
        if self.screens.current in ("dashboard", "my_complaints", "notifications"):
            self.detail_origin = self.screens.current
        self.detail_version += 1
        request_version = self.detail_version
        self.detail.show_loading(ticket_id)
        self.navigate("complaint_detail", "left")

        def show_if_current(data, error):
            if request_version != self.detail_version or self.screens.current != "complaint_detail":
                return
            if error == 403:
                self.detail.show_error("This complaint is not available to your account.", allow_retry=False)
            elif error == 404:
                self.detail.show_error("This complaint no longer exists.", allow_retry=False)
            elif error is not None or not isinstance(data, dict) or data.get("id") != ticket_id or any(
                not isinstance(data.get(field), str)
                for field in ("title", "status", "category_name", "location", "description")
            ):
                self.detail.show_error("Could not load the complaint. Try again in a moment.")
            else:
                self.detail.show_complaint(data)
                self.load_comments(ticket_id, "student")
                self.load_reopen_history(ticket_id)

        self.call("GET", f"/api/complaints/{ticket_id}", 200, show_if_current, protected=True)

    def close_detail(self, _button):
        self.detail_version += 1
        self.detail.clear()
        if self.detail_origin == "my_complaints":
            self.navigate("my_complaints", "right")
            self.load_complaints(force=True)
        elif self.detail_origin == "notifications":
            self.navigate("notifications", "right")
            self.load_notifications()
            self.load_notification_count()
        else:
            self.open_dashboard(None)

    def load_complaints(self, *_, force=False):
        if (not self.token or not self.user or self.user.get("role") != "Student"
                or (self.list_loading and not force)):
            return
        self.list_loading = True
        self.list_version += 1
        request_version = self.list_version
        self.dashboard.show_message("Loading your complaints...")
        self.my_complaints.show_message("Loading your complaints...")

        def latest_response(data, error):
            if request_version == self.list_version:
                self.finish_loading(data, error)

        self.call("GET", "/api/complaints/mine", 200, latest_response, protected=True)

    def finish_loading(self, data, error):
        self.list_loading = False
        if error == 403:
            message = "Only student accounts can open this list."
        elif error is not None or not isinstance(data, list) or any(
            not isinstance(row, dict) or not all(
                key in row for key in ("id", "title", "category_name", "status")
            ) for row in data
        ):
            message = "Could not load your complaints. Tap Refresh to try again."
        else:
            self.dashboard.show_complaints(data[:4])  # Recent tickets stay compact.
            self.my_complaints.set_rows(data)           # Full list on its own screen.
            return
        self.dashboard.show_message(message)
        self.my_complaints.show_message(message)

    def complaint_saved(self, complaint_id):
        self.dashboard.show_notice(f"Complaint #{complaint_id} saved.")
        self.navigate("dashboard", "right")
        self.load_complaints(force=True)


if __name__ == "__main__":
    CampusFixApp().run()
