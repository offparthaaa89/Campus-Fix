"""CampusFix Fixline — standalone visual prototype.

Run from the CampusFix project root:
    python design_lab/fixline_preview.py

This deliberately does NOT connect to FastAPI/PostgreSQL or change frontend/main.py.
All tickets, messages, counts and actions are fictional demonstration data.
Requires only Kivy, already installed in your project's .venv.
"""

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform


def rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)


INK = '#183B32'
DEEP = '#153A31'
LIME = '#E0F69B'
CREAM = '#F5F6F0'
WHITE = '#FFFFFF'
MUTED = '#677A70'
LINE = '#DFE6DC'
PASTELS = {
    'wifi': '#E5E9FC', 'hostel': '#FBE9D8', 'electrical': '#FFF0C6',
    'cleanliness': '#DCF2E6', 'classroom': '#F8E1DB', 'other': '#E8ECE9',
}
CATEGORIES = [
    ('wifi', 'Wi-Fi / IT', 'Internet and devices'),
    ('hostel', 'Hostel', 'Rooms and facilities'),
    ('electrical', 'Electrical', 'Power, lights and fans'),
    ('cleanliness', 'Cleanliness', 'Cleaning and hygiene'),
    ('classroom', 'Classroom', 'Learning spaces'),
    ('other', 'Something else', 'Other campus problems'),
]


def paint(widget, bg, radius=16):
    with widget.canvas.before:
        color = Color(*rgb(bg))
        rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])

    def sync(*_):
        color.rgba = rgb(bg)
        rect.pos = widget.pos
        rect.size = widget.size
        rect.radius = [dp(radius)]

    widget.bind(pos=sync, size=sync)
    return widget


def text(message, size=16, color=INK, bold=False, height=32, align='left'):
    lbl = Label(text=message, font_size=sp(size), color=rgb(color), bold=bold,
                halign=align, valign='middle', size_hint_y=None, height=dp(height),
                shorten=False, markup=False)
    lbl.bind(width=lambda obj, width: setattr(obj, 'text_size', (width, None)))
    return lbl


def stack(spacing=12, padding=0):
    return BoxLayout(orientation='vertical', spacing=dp(spacing), padding=dp(padding),
                     size_hint_y=None)


def row(height=52, spacing=12):
    return BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(height),
                     spacing=dp(spacing))


def card(bg=WHITE, padding=18, gap=12, radius=18):
    widget = stack(gap, padding)
    paint(widget, bg, radius)
    widget.bind(minimum_height=widget.setter('height'))
    return widget


def divider():
    rule = Widget(size_hint_y=None, height=dp(1))
    with rule.canvas:
        Color(*rgb(LINE))
        rect = RoundedRectangle(pos=rule.pos, size=rule.size)
    rule.bind(pos=lambda obj, *_: setattr(rect, 'pos', obj.pos),
              size=lambda obj, *_: setattr(rect, 'size', obj.size))
    return rule


class BrandMark(Widget):
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
            Color(*rgb(LIME))
            RoundedRectangle(pos=(x, y), size=(side, side), radius=[side * .24])
            Color(*rgb(DEEP))
            # A single routed line suggests campus wayfinding and progress.
            Line(points=[*point(.70, .75), *point(.40, .75),
                         *point(.28, .63), *point(.28, .34), *point(.49, .34)],
                 width=max(dp(2.4), side * .078), cap='round', joint='round')
            Ellipse(pos=(x + side * .65, y + side * .70),
                    size=(side * .10, side * .10))
            # The check is the visual promise of CampusFix: resolved.
            Line(points=[*point(.50, .43), *point(.62, .31), *point(.83, .58)],
                 width=max(dp(2.6), side * .085), cap='round', joint='round')


def brand_lockup(icon_size=42):
    header = row(max(48, icon_size + 4), 10)
    header.add_widget(BrandMark(size_hint=(None, None),
                                size=(dp(icon_size), dp(icon_size))))
    header.add_widget(text('CampusFix', 23 if icon_size >= 42 else 20,
                           WHITE, True, max(48, icon_size + 4)))
    return header


class FlatButton(Button):
    def __init__(self, label, bg=DEEP, fg=WHITE, h=50, radius=14, **kwargs):
        super().__init__(text=label, size_hint_y=None, height=dp(h),
                         font_size=sp(14), bold=True, color=rgb(fg),
                         background_normal='', background_down='',
                         background_color=(0, 0, 0, 0), **kwargs)
        paint(self, bg, radius)


class Icon(Widget):
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
            Color(*rgb(self.ink))
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


def iconbox(kind, bg, size=64, icon_size=34):
    outer = BoxLayout(size_hint=(None, None), width=dp(size), height=dp(size),
                      padding=dp((size-icon_size)/2))
    paint(outer, bg, 15)
    outer.add_widget(Icon(kind, size_hint=(1,1)))
    return outer


class Tile(ButtonBehavior, BoxLayout):
    def __init__(self, kind, label, hint, on_pick, **kwargs):
        super().__init__(orientation='vertical', padding=dp(15), spacing=dp(8), **kwargs)
        paint(self, PASTELS[kind], 18)
        header = row(47)
        header.add_widget(Icon(kind, size_hint=(None,1), width=dp(43)))
        header.add_widget(Widget())
        arrow = Icon('arrow', color='#668176', size_hint=(None,1),width=dp(23))
        header.add_widget(arrow)
        self.add_widget(header)
        self.add_widget(text(label, 16, INK, True, 28))
        self.add_widget(text(hint, 11, MUTED, False, 26))
        self.bind(on_release=lambda *_: on_pick(kind))


class Fixline(Widget):
    """A distinctive, readable progress route in the CampusFix identity."""
    def __init__(self, progress=2, **kwargs):
        super().__init__(size_hint_y=None, height=dp(70), **kwargs)
        self.progress = progress
        self.bind(pos=self.draw, size=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        x,y=self.pos
        w,h=self.size
        cx=[x+w*(.08+i*.28) for i in range(4)]
        mid=y+h*.52
        with self.canvas:
            Color(*rgb('#618478'))
            Line(points=[cx[0],mid,cx[3],mid],width=dp(5),cap='round')
            Color(*rgb(LIME))
            Line(points=[cx[0],mid,cx[self.progress],mid],width=dp(5),cap='round')
            for i,v in enumerate(cx):
                Color(*rgb(LIME if i<=self.progress else '#9CB4A4'))
                Ellipse(pos=(v-dp(8),mid-dp(8)),size=(dp(16),dp(16)))
                if i<=self.progress:
                    Color(*rgb(DEEP))
                    Ellipse(pos=(v-dp(3),mid-dp(3)),size=(dp(6),dp(6)))


class FixlineApp(App):
    def build(self):
        self.title = 'CampusFix'
        if platform in ('win', 'linux', 'macosx'):
            Window.size = (1050, 790)
        Window.clearcolor = rgb(CREAM)
        self.role = 'student'
        self.page = 'home'
        self.category = 'wifi'
        self.report_title = ''
        self.report_location = ''
        self.report_description = ''
        self.staff_status = 'Open'
        self.assigned = False
        self.assignee = 'Maintenance Staff'
        self.root_panel = BoxLayout(orientation='horizontal')
        self.was_mobile = Window.width < dp(790)
        Window.bind(size=self.on_window_resize)
        self.render()
        return self.root_panel

    def on_window_resize(self, *_):
        mobile = Window.width < dp(790)
        if mobile != self.was_mobile:
            self.was_mobile = mobile
            self.render()

    def switch_role(self, role):
        self.role, self.page = role, 'home'
        self.render()

    def navigate(self, page):
        self.page = page
        self.render()

    def new_issue(self, kind):
        self.category, self.page = kind, 'form'
        self.report_title = next((name for key,name,_ in CATEGORIES if key==kind), 'Campus issue') + ' issue'
        self.report_location = ''
        self.report_description = ''
        self.render()

    def render(self):
        self.root_panel.clear_widgets()
        wide = Window.width >= dp(790)
        if wide:
            self.root_panel.add_widget(self.sidebar())
        self.root_panel.add_widget(self.main_view(wide))

    def sidebar(self):
        nav = card(DEEP, 23, 14, radius=0)
        nav.size_hint_x = None
        nav.width = dp(240)
        nav.size_hint_y = 1
        nav.add_widget(brand_lockup(42))
        nav.add_widget(Widget(size_hint_y=None, height=dp(32)))
        nav.add_widget(text('EXPLORE AS', 11, '#B2CDBB', True, 25))
        for code, name in [('student','Student'),('staff','Staff'),('admin','Admin')]:
            b = FlatButton(('●  ' if self.role==code else '   ')+name,
                           bg=LIME if self.role==code else '#295247',
                           fg=DEEP if self.role==code else WHITE, h=50)
            b.bind(on_release=lambda _, r=code: self.switch_role(r))
            nav.add_widget(b)
        nav.add_widget(Widget())
        nav.add_widget(divider())
        nav.add_widget(text('DESIGN RULES', 11, LIME, True, 24))
        nav.add_widget(text('Recognize the issue.\nTake one clear action.\nFollow the journey.', 12, '#DEEBDF', height=75))
        nav.add_widget(text('Prototype • sample data only', 10, '#B2CDBB', height=24))
        return nav

    def main_view(self, wide):
        area = BoxLayout(orientation='vertical')
        if not wide:
            # Compact single-row header: the product name is simply CampusFix.
            # Role picker exists for this offline design lab only; real app uses login.
            top = BoxLayout(orientation='horizontal', spacing=dp(9),
                            padding=[dp(13), dp(10), dp(13), dp(10)],
                            size_hint_y=None, height=dp(70))
            paint(top, DEEP, 0)
            top.add_widget(brand_lockup(40))
            picker = Spinner(text=self.role.title(),
                             values=['Student', 'Staff', 'Admin'],
                             size_hint=(None, None), width=dp(105), height=dp(38),
                             background_normal='', background_down='',
                             background_color=rgb(LIME), color=rgb(DEEP),
                             font_size=sp(13), bold=True)
            picker.bind(text=lambda _, label: self.switch_role(label.lower())
                        if label.lower() != self.role else None)
            top.add_widget(picker)
            area.add_widget(top)
        scroll=ScrollView(do_scroll_x=False, bar_width=dp(4), scroll_type=['bars','content'])
        content=stack(17, 22 if wide else 13)
        content.bind(minimum_height=content.setter('height'))
        if wide:
            content.add_widget(text(self.role.upper() + ' WORKSPACE', 11, MUTED, True, 24))
        if self.role=='student':
            self.student_screen(content,wide)
        elif self.role=='staff':
            self.staff_screen(content,wide)
        else:
            self.admin_screen(content,wide)
        content.add_widget(text('DESIGN PREVIEW  •  No changes to your real CampusFix database.',
                                11,MUTED, height=46))
        scroll.add_widget(content)
        area.add_widget(scroll)
        return area

    def hero(self, eyebrow, title, subtitle, progress=None):
        compact = Window.width < dp(790)
        header = card(DEEP, 19 if compact else 24, 7 if compact else 10, 22)
        header.add_widget(text(eyebrow, 10 if compact else 11, LIME, True, 20 if compact else 24))
        header.add_widget(text(title, 23 if compact else 29, WHITE, True, 66 if compact else 74))
        header.add_widget(text(subtitle, 13 if compact else 14, '#DEEBDF', False,
                               46 if compact else 54))
        if progress is not None:
            header.add_widget(Fixline(progress=progress))
            labels=row(23)
            for word in ['REPORT','ASSIGN','FIX','DONE']:
                labels.add_widget(text(word,10,LIME if word in ('REPORT','ASSIGN','FIX') else '#ADC5B5',True,23,'center'))
            header.add_widget(labels)
        return header

    def student_screen(self, content, wide):
        if self.page=='home':
            content.add_widget(self.hero('THE CAMPUS HELP DESK', 'See it. Report it. Fix it.',
                                         'Tap a sign below to report a campus issue.'))
            titlebar=row(42)
            titlebar.add_widget(text('What needs fixing?',22,INK,True,42))
            titlebar.add_widget(text('TAP A SIGN',10,MUTED,True,42,'right'))
            content.add_widget(titlebar)
            tiles=GridLayout(cols=3 if wide else 2,spacing=dp(12),size_hint_y=None,
                             row_default_height=dp(147),row_force_default=True)
            tiles.bind(minimum_height=tiles.setter('height'))
            for kind,name,hint in CATEGORIES:
                tiles.add_widget(Tile(kind,name,hint,self.new_issue))
            content.add_widget(tiles)
            follow=card(WHITE,18,10)
            r=row(57)
            r.add_widget(iconbox('route','#E7F1DD',size=52,icon_size=30))
            labels=stack(1)
            labels.add_widget(text('Follow your fixes',17,INK,True,30))
            labels.add_widget(text('Know exactly where your requests stand',12,MUTED,height=26))
            labels.bind(minimum_height=labels.setter('height'))
            r.add_widget(labels)
            btn=FlatButton('View  →',bg=LIME,fg=DEEP,h=45)
            btn.size_hint_x=None
            btn.width=dp(100)
            btn.bind(on_release=lambda *_:self.navigate('track'))
            r.add_widget(btn)
            follow.add_widget(r)
            content.add_widget(follow)
        elif self.page=='form':
            self.back(content,'Back to issue signs','home')
            cat=next(n for k,n,_ in CATEGORIES if k==self.category)
            banner=card(PASTELS[self.category],18,5)
            rr=row(65)
            rr.add_widget(iconbox(self.category,PASTELS[self.category],size=65,icon_size=50))
            rr.add_widget(text(cat+'  /  Selected issue',18,INK,True,65))
            banner.add_widget(rr)
            content.add_widget(banner)
            content.add_widget(text('Tell us a little more.',26,INK,True,63))
            form=card(WHITE,20,11)
            form.add_widget(text('WHAT HAPPENED?',11,MUTED,True,25))
            titleinput=self.input_box(self.report_title,'Short issue title')
            form.add_widget(titleinput)
            form.add_widget(text('WHERE SHOULD WE LOOK?',11,MUTED,True,25))
            placeinput=self.input_box(self.report_location,'e.g. Hostel B, Room 12')
            form.add_widget(placeinput)
            form.add_widget(text('ANYTHING ELSE WE SHOULD KNOW?',11,MUTED,True,25))
            detailinput=self.input_box(self.report_description,'Describe what is not working...',multiline=True)
            form.add_widget(detailinput)
            info=text('Category already selected. Your report will remain a preview in this design lab.',11,MUTED,height=48)
            form.add_widget(info)
            submit=FlatButton('Review report   →',h=54)
            submit.bind(on_release=lambda *_:self.save_preview(titleinput.text,placeinput.text,detailinput.text,info))
            form.add_widget(submit)
            content.add_widget(form)
        elif self.page=='review':
            self.back(content,'Edit report','form')
            content.add_widget(self.hero('REPORT PREVIEW','Ready to report?',
                                         'Review your information before submitting.',0))
            summ=card(WHITE,22,13)
            cat=next(n for k,n,_ in CATEGORIES if k==self.category)
            rr=row(68)
            rr.add_widget(iconbox(self.category,PASTELS[self.category]))
            rr.add_widget(text(cat,18,INK,True,60))
            summ.add_widget(rr)
            summ.add_widget(divider())
            for label,value in [('ISSUE',self.report_title),('LOCATION',self.report_location),('DETAILS',self.report_description)]:
                summ.add_widget(text(label,10,MUTED,True,21))
                summ.add_widget(text(value,15,INK,height=51))
            summ.add_widget(text('Demo only — this button will NOT create a real complaint.',11,MUTED,height=45))
            b=FlatButton('Explore the tracking design   →')
            b.bind(on_release=lambda *_:self.navigate('track'))
            summ.add_widget(b)
            content.add_widget(summ)
        else:
            self.back(content,'Back to issue signs','home')
            content.add_widget(self.hero('SAMPLE TICKET  /  #104','Your fix is on its way.',
                                         'A visual journey tells you what is happening.',2))
            ticket=card(WHITE,22,12)
            rr=row(60)
            rr.add_widget(iconbox('wifi',PASTELS['wifi'],size=58))
            rr.add_widget(text('Hostel Wi-Fi not working',19,INK,True,60))
            ticket.add_widget(rr)
            ticket.add_widget(divider())
            for i,(name,note) in enumerate([
                ('Reported','Your report reached CampusFix'),
                ('Assigned','The IT support team received it'),
                ('Being fixed','Staff is working on the issue'),
                ('Resolved','You will be notified when complete'),
            ]):
                rr=row(63)
                rr.add_widget(iconbox('check' if i<3 else 'route',
                                     '#DDF3E2' if i<3 else '#E9ECE7',size=44,icon_size=25))
                note_stack=stack(0)
                note_stack.add_widget(text(name,16,INK,True,29))
                note_stack.add_widget(text(note,12,MUTED,height=30))
                note_stack.bind(minimum_height=note_stack.setter('height'))
                rr.add_widget(note_stack)
                ticket.add_widget(rr)
            ticket.add_widget(divider())
            ticket.add_widget(text('Messages, notifications and reopen requests will be kept inside this ticket.',
                                   12,MUTED,height=54))
            content.add_widget(ticket)

    def input_box(self,value,hint,multiline=False):
        return TextInput(text=value,hint_text=hint,multiline=multiline,
                         size_hint_y=None,height=dp(105 if multiline else 52),
                         background_normal='',background_active='',
                         background_color=rgb(CREAM),foreground_color=rgb(INK),
                         hint_text_color=rgb('#819087'),font_size=sp(15),
                         padding=(dp(14),dp(15)),cursor_color=rgb(INK))

    def save_preview(self, title, place, description, info):
        if not all(v.strip() for v in (title,place,description)):
            info.text='Please fill in all three fields to review the report.'
            info.color=rgb('#A14236')
            return
        self.report_title, self.report_location, self.report_description=title.strip(),place.strip(),description.strip()
        self.navigate('review')

    def back(self, content, label, target):
        btn=FlatButton('←   '+label,bg='#E5EAE1',fg=INK,h=42)
        btn.size_hint_x=None
        btn.width=dp(230)
        btn.bind(on_release=lambda *_:self.navigate(target))
        content.add_widget(btn)

    def staff_screen(self, content, wide):
        content.add_widget(self.hero('STAFF  /  THE WORKBENCH','Your next fix.',
                                     'No busy dashboard. One clear task at a time.'))
        content.add_widget(text('Assigned to you',23,INK,True,46))
        job=card(WHITE,21,13)
        heading=row(67)
        heading.add_widget(iconbox('wifi',PASTELS['wifi'],size=63))
        job_name=stack(3)
        job_name.add_widget(text('REQUEST #104',11,MUTED,True,23))
        job_name.add_widget(text('Hostel Wi-Fi',21,INK,True,35))
        job_name.bind(minimum_height=job_name.setter('height'))
        heading.add_widget(job_name)
        job.add_widget(heading)
        rr=row(36)
        rr.add_widget(Icon('pin',color=MUTED,size_hint_x=None,width=dp(26)))
        rr.add_widget(text('Hostel B · Room 12',14,MUTED,height=36))
        job.add_widget(rr)
        job.add_widget(divider())
        job.add_widget(text('CURRENT STATUS',10,MUTED,True,25))
        job.add_widget(text(self.staff_status,20,INK,True,40))
        note={'Open':'Start working to move this request forward.',
              'In Progress':'Mark done after the repair is complete.',
              'Resolved':'This request is complete in the prototype.'}[self.staff_status]
        job.add_widget(text(note,13,MUTED,height=43))
        action=FlatButton({'Open':'Start working  →','In Progress':'Mark as resolved  ✓',
                           'Resolved':'Reset demonstration'}[self.staff_status],h=54)
        action.bind(on_release=lambda *_:self.staff_next())
        job.add_widget(action)
        job.add_widget(divider())
        job.add_widget(text('Staff replies, status history and reopen decisions will remain within ticket details.',
                            12,MUTED,height=53))
        content.add_widget(job)
        secondary=card('#E7EEE7',17,5)
        secondary.add_widget(text('What about my other requests?',15,INK,True,34))
        secondary.add_widget(text('In the production interface, scroll for the rest of your assigned queue and unresolved filters.',
                                  12,MUTED,height=53))
        content.add_widget(secondary)

    def staff_next(self):
        self.staff_status={'Open':'In Progress','In Progress':'Resolved','Resolved':'Open'}[self.staff_status]
        self.render()

    def admin_screen(self, content, wide):
        content.add_widget(self.hero('ADMIN  /  THE DISPATCH DESK','Keep campus moving.',
                                     'Unassigned requests first. Workloads next.'))
        counts=GridLayout(cols=3,spacing=dp(10),size_hint_y=None,height=dp(98))
        for title,value in [('NEEDS OWNER','0' if self.assigned else '1'),('ACTIVE','4'),('DONE','12')]:
            tile=card(WHITE,13,5)
            tile.add_widget(text(title,10,MUTED,True,25))
            tile.add_widget(text(value,26,INK,True,44))
            counts.add_widget(tile)
        content.add_widget(counts)
        content.add_widget(text('Needs dispatch',22,INK,True,43))
        job=card(WHITE,20,13)
        rr=row(68)
        rr.add_widget(iconbox('electrical',PASTELS['electrical'],size=64))
        details=stack(0)
        details.add_widget(text('REQUEST #108  ·  ELECTRICAL',11,MUTED,True,26))
        details.add_widget(text('Fan not working',19,INK,True,34))
        details.bind(minimum_height=details.setter('height'))
        rr.add_widget(details)
        job.add_widget(rr)
        job.add_widget(text('Classroom 204',13,MUTED,height=35))
        job.add_widget(divider())
        if self.assigned:
            job.add_widget(text('✓  Assigned to '+self.assignee,16,'#28775B',True,47))
            btn=FlatButton('Reset assignment demo',bg='#E5EAE1',fg=INK)
            btn.bind(on_release=lambda *_:self.assign(False))
            job.add_widget(btn)
        else:
            job.add_widget(text('WHO SHOULD HANDLE THIS?',11,MUTED,True,28))
            spinner=Spinner(text=self.assignee,values=['Maintenance Staff','Electrical Support'],
                            size_hint_y=None,height=dp(52),
                            background_normal='',background_down='',
                            background_color=rgb('#E4EEE4'),color=rgb(INK),
                            font_size=sp(16))
            spinner.bind(text=lambda _, v: setattr(self,'assignee',v))
            job.add_widget(spinner)
            btn=FlatButton('Assign request   →',h=54)
            btn.bind(on_release=lambda *_:self.assign(True))
            job.add_widget(btn)
        content.add_widget(job)
        foot=card('#E6EEE5',17,6)
        foot.add_widget(text('More tools, only when needed',16,INK,True,32))
        foot.add_widget(text('Full complaint filters, category statistics, overdue issues and reopen approvals are accessible from the dispatch workspace.',
                             12,MUTED,height=62))
        content.add_widget(foot)

    def assign(self, value):
        self.assigned=value
        self.render()


if __name__ == '__main__':
    FixlineApp().run()
