#!/usr/bin/env python3
"""AI Office Simulation - Top-down 3D style with AI Agents"""

import pygame
import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

pygame.init()

# ── Constants ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 800
FPS = 60
TILE = 48

# Palette
C_BG       = (240, 235, 225)
C_FLOOR    = (210, 200, 185)
C_FLOOR2   = (220, 212, 198)
C_WALL     = (140, 120, 100)
C_WALL_TOP = (160, 145, 125)
C_DESK     = (180, 140, 90)
C_DESK_TOP = (200, 160, 110)
C_DESK_SHADOW = (150, 115, 70)
C_SCREEN   = (80, 180, 230)
C_SCREEN_GLOW = (120, 200, 255)
C_CABINET  = (150, 120, 80)
C_CABINET_TOP = (170, 140, 100)
C_MEETING  = (160, 200, 140)
C_MEETING_TOP = (180, 220, 160)
C_PLANT    = (80, 160, 80)
C_PLANT_POT = (160, 100, 60)
C_COFFEE   = (120, 80, 40)
C_WHITE    = (255, 255, 255)
C_BLACK    = (20, 20, 20)
C_SHADOW   = (0, 0, 0, 60)

AGENT_COLORS = {
    "Planner":  (220,  80,  80),
    "Analyst":  ( 80, 140, 220),
    "Dev":      ( 80, 200, 120),
    "Manager":  (200, 160,  40),
    "Designer": (180,  80, 200),
}

AGENT_COLORS_DARK = {k: tuple(max(0, c - 60) for c in v) for k, v in AGENT_COLORS.items()}

# ── Enums ──────────────────────────────────────────────────────────────────────
class AgentState(Enum):
    IDLE    = "idle"
    MOVING  = "moving"
    WORKING = "working"
    MEETING = "meeting"
    FETCHING = "fetching"
    COFFEE  = "coffee"

# ── Isometric helpers ──────────────────────────────────────────────────────────
ORIGIN_X = 200
ORIGIN_Y = 120

def iso(gx, gy, gz=0):
    sx = (gx - gy) * TILE + ORIGIN_X
    sy = (gx + gy) * (TILE // 2) - gz * (TILE // 2) + ORIGIN_Y
    return sx, sy

# ── Speech Bubble ──────────────────────────────────────────────────────────────
@dataclass
class Bubble:
    text: str
    x: float
    y: float
    lifetime: float = 3.5
    age: float = 0.0
    color: tuple = (255, 255, 255)

    def update(self, dt):
        self.age += dt

    @property
    def alive(self):
        return self.age < self.lifetime

    @property
    def alpha(self):
        fade = 0.5
        t = self.age / self.lifetime
        if t > (1 - fade):
            return int(255 * (1 - (t - (1 - fade)) / fade))
        return 255


def draw_bubble(surf, bubble, font_small):
    lines = []
    words = bubble.text.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if font_small.size(test)[0] > 200:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)

    lh = font_small.get_linesize() + 2
    bw = max(font_small.size(l)[0] for l in lines) + 16
    bh = lh * len(lines) + 10

    alpha = bubble.alpha
    bx = int(bubble.x - bw // 2)
    by = int(bubble.y - bh - 14)

    tmp = pygame.Surface((bw + 4, bh + 12), pygame.SRCALPHA)
    # Shadow
    pygame.draw.roundrect = None
    shadow_rect = pygame.Rect(4, 4, bw, bh)
    pygame.draw.rect(tmp, (0, 0, 0, 60), shadow_rect, border_radius=8)
    # Body
    body_rect = pygame.Rect(0, 0, bw, bh)
    pygame.draw.rect(tmp, (*bubble.color, alpha), body_rect, border_radius=8)
    pygame.draw.rect(tmp, (100, 100, 100, alpha), body_rect, 1, border_radius=8)
    # Tail
    pts = [(bw // 2 - 5, bh), (bw // 2 + 5, bh), (bw // 2, bh + 10)]
    pygame.draw.polygon(tmp, (*bubble.color, alpha), pts)
    pygame.draw.polygon(tmp, (100, 100, 100, alpha), pts, 1)
    # Text
    for i, l in enumerate(lines):
        txt_surf = font_small.render(l, True, (30, 30, 30))
        txt_surf.set_alpha(alpha)
        tmp.blit(txt_surf, (8, 5 + i * lh))

    surf.blit(tmp, (bx, by))


# ── Agent ──────────────────────────────────────────────────────────────────────
@dataclass
class Agent:
    name: str
    role: str
    gx: float
    gy: float
    desk: tuple
    color: tuple = field(default_factory=lambda: (200, 100, 100))
    color_dark: tuple = field(default_factory=lambda: (140, 60, 60))
    state: AgentState = AgentState.IDLE
    target: Optional[tuple] = None
    task: str = ""
    bubble: Optional[Bubble] = None
    anim: float = 0.0
    walk_cycle: float = 0.0
    busy_timer: float = 0.0

    def say(self, text, lifetime=3.5):
        sx, sy = iso(self.gx, self.gy)
        self.bubble = Bubble(text, sx, sy - 20, lifetime,
                             color=(255, 252, 230))

    def set_target(self, gx, gy):
        self.target = (gx, gy)
        self.state = AgentState.MOVING

    def update(self, dt):
        self.anim += dt
        if self.bubble:
            self.bubble.update(dt)
            sx, sy = iso(self.gx, self.gy)
            self.bubble.x = sx
            self.bubble.y = sy - 20
            if not self.bubble.alive:
                self.bubble = None

        if self.state == AgentState.MOVING and self.target:
            tx, ty = self.target
            dx, dy = tx - self.gx, ty - self.gy
            dist = math.hypot(dx, dy)
            speed = 2.5 * dt
            if dist < speed + 0.05:
                self.gx, self.gy = tx, ty
                self.target = None
                self.state = AgentState.WORKING
                self.walk_cycle = 0
            else:
                self.gx += dx / dist * speed
                self.gy += dy / dist * speed
                self.walk_cycle += dt * 8

        if self.busy_timer > 0:
            self.busy_timer -= dt
            if self.busy_timer <= 0:
                self.state = AgentState.IDLE

    def draw(self, surf):
        sx, sy = iso(self.gx, self.gy)
        # Shadow
        shad = pygame.Surface((28, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0, 0, 0, 50), shad.get_rect())
        surf.blit(shad, (sx - 14, sy + 4))

        bob = math.sin(self.anim * 3) * 2 if self.state == AgentState.WORKING else 0
        leg_off = math.sin(self.walk_cycle) * 4 if self.state == AgentState.MOVING else 0

        # Body (isometric cylinder-ish)
        body_y = sy - 28 + bob
        # Legs
        pygame.draw.line(surf, self.color_dark,
                         (sx - 4, body_y + 22), (sx - 4 + int(leg_off), body_y + 32), 4)
        pygame.draw.line(surf, self.color_dark,
                         (sx + 4, body_y + 22), (sx + 4 - int(leg_off), body_y + 32), 4)
        # Body
        pygame.draw.ellipse(surf, self.color,
                            (sx - 12, body_y + 8, 24, 18))
        # Head
        pygame.draw.circle(surf, self.color, (sx, body_y + 4), 11)
        pygame.draw.circle(surf, self.color_dark, (sx, body_y + 4), 11, 2)
        # Eyes
        pygame.draw.circle(surf, C_WHITE, (sx - 4, body_y + 2), 3)
        pygame.draw.circle(surf, C_WHITE, (sx + 4, body_y + 2), 3)
        pygame.draw.circle(surf, C_BLACK, (sx - 4, body_y + 3), 1)
        pygame.draw.circle(surf, C_BLACK, (sx + 4, body_y + 3), 1)

        # State indicator dot
        dot_colors = {
            AgentState.IDLE: (150, 150, 150),
            AgentState.WORKING: (80, 220, 80),
            AgentState.MOVING: (220, 180, 80),
            AgentState.MEETING: (80, 150, 220),
            AgentState.FETCHING: (200, 120, 40),
            AgentState.COFFEE: (140, 100, 60),
        }
        pygame.draw.circle(surf, dot_colors.get(self.state, C_WHITE),
                           (sx + 10, body_y - 6), 5)
        pygame.draw.circle(surf, C_WHITE, (sx + 10, body_y - 6), 5, 1)

    def draw_bubble(self, surf, font):
        if self.bubble:
            draw_bubble(surf, self.bubble, font)


# ── Office Layout drawing ──────────────────────────────────────────────────────
def draw_floor(surf):
    for gx in range(12):
        for gy in range(10):
            pts = [iso(gx, gy), iso(gx+1, gy), iso(gx+1, gy+1), iso(gx, gy+1)]
            c = C_FLOOR if (gx + gy) % 2 == 0 else C_FLOOR2
            pygame.draw.polygon(surf, c, pts)
            pygame.draw.polygon(surf, (190, 180, 165), pts, 1)


def draw_iso_box(surf, gx, gy, w, d, h, top_c, left_c, right_c):
    # Top face
    top = [iso(gx, gy, h), iso(gx+w, gy, h), iso(gx+w, gy+d, h), iso(gx, gy+d, h)]
    pygame.draw.polygon(surf, top_c, top)
    pygame.draw.polygon(surf, (0, 0, 0, 30), top, 1)
    # Left face
    left = [iso(gx, gy, 0), iso(gx, gy+d, 0), iso(gx, gy+d, h), iso(gx, gy, h)]
    pygame.draw.polygon(surf, left_c, left)
    # Right face
    right = [iso(gx, gy+d, 0), iso(gx+w, gy+d, 0), iso(gx+w, gy+d, h), iso(gx, gy+d, h)]
    pygame.draw.polygon(surf, right_c, right)


def darken(c, amt=40):
    return tuple(max(0, x - amt) for x in c[:3])


def draw_office(surf):
    draw_floor(surf)

    # Walls (top and left border)
    for i in range(12):
        draw_iso_box(surf, i, 0, 1, 0.2, 3,
                     C_WALL_TOP, C_WALL, darken(C_WALL, 20))
    for i in range(10):
        draw_iso_box(surf, 0, i, 0.2, 1, 3,
                     C_WALL_TOP, C_WALL, darken(C_WALL, 20))

    # Desks (5 agent desks)
    desk_positions = [
        (2, 2), (5, 2), (8, 2),
        (2, 5), (5, 5),
    ]
    for gx, gy in desk_positions:
        draw_iso_box(surf, gx, gy, 1.8, 1.2, 1,
                     C_DESK_TOP, C_DESK, darken(C_DESK, 30))
        # Monitor
        draw_iso_box(surf, gx + 0.3, gy + 0.1, 0.9, 0.15, 1.6,
                     C_SCREEN_GLOW, C_SCREEN, darken(C_SCREEN, 30))

    # Meeting table (center right)
    draw_iso_box(surf, 7, 5, 2.5, 2, 0.8,
                 C_MEETING_TOP, C_MEETING, darken(C_MEETING, 30))

    # File cabinet
    draw_iso_box(surf, 10, 2, 1, 1.5, 2,
                 C_CABINET_TOP, C_CABINET, darken(C_CABINET, 30))
    # Cabinet drawers
    for i in range(3):
        h_off = i * 0.5
        pts = [iso(10, 2 + h_off/2, 0.3 + h_off),
               iso(11, 2 + h_off/2, 0.3 + h_off),
               iso(11, 2 + h_off/2 + 0.7, 0.3 + h_off),
               iso(10, 2 + h_off/2 + 0.7, 0.3 + h_off)]
        pygame.draw.polygon(surf, (180, 150, 110, 80), pts, 1)
        # Handle
        mx = (pts[0][0] + pts[1][0]) // 2
        my = (pts[0][1] + pts[1][1]) // 2
        pygame.draw.circle(surf, (200, 170, 100), (mx, my + 3), 3)

    # Coffee machine
    draw_iso_box(surf, 10, 7, 0.8, 0.8, 1.5,
                 C_COFFEE, darken(C_COFFEE, 20), darken(C_COFFEE, 40))
    # Coffee light
    pygame.draw.circle(surf, (255, 100, 50),
                       (iso(10.4, 7.4, 1.5)[0], iso(10.4, 7.4, 1.5)[1] + 4), 4)

    # Plants (corners)
    for gx, gy in [(1.5, 8.5), (10.5, 0.8)]:
        sx, sy = iso(gx, gy)
        # Pot
        pygame.draw.ellipse(surf, C_PLANT_POT, (sx-8, sy-6, 16, 12))
        # Leaves
        for angle in range(0, 360, 60):
            rad = math.radians(angle)
            ex = sx + math.cos(rad) * 12
            ey = sy - 20 + math.sin(rad) * 6
            pygame.draw.circle(surf, C_PLANT, (int(ex), int(ey)), 7)
        pygame.draw.circle(surf, darken(C_PLANT, 20), (sx, sy - 18), 9)


# ── Scenarios ──────────────────────────────────────────────────────────────────
SCENARIOS = {
    "Product Launch": [
        ("Planner",  "office_fetching", (10.5, 3.0), "Collecting market data..."),
        ("Analyst",  "desk",             None,        "Analyzing sales figures..."),
        ("Dev",      "desk",             None,        "Building launch dashboard..."),
        ("Manager",  "meeting",          (8.3, 6.5),  "Scheduling team meeting!"),
        ("Designer", "desk",             None,        "Creating UI mockups..."),
        ("Planner",  "meeting",          (8.3, 5.8),  "Meeting: Launch in 3 days!"),
        ("Analyst",  "meeting",          (7.5, 6.8),  "Market risk: LOW ✓"),
        ("Dev",      "meeting",          (9.0, 6.2),  "Feature complete!"),
        ("Designer", "meeting",          (7.8, 5.5),  "Designs approved!"),
        ("Manager",  "desk",             None,        "Sending launch report..."),
        ("Planner",  "desk",             None,        "Launch plan finalized!"),
    ],
    "Bug Crisis": [
        ("Planner",  "desk",             None,        "ALERT: Critical bug detected!"),
        ("Dev",      "office_fetching",  (10.5, 2.5), "Pulling error logs..."),
        ("Analyst",  "desk",             None,        "Tracing the stack trace..."),
        ("Dev",      "desk",             None,        "Found the bug! Line 247..."),
        ("Planner",  "meeting",          (8.5, 6.0),  "Emergency meeting NOW!"),
        ("Analyst",  "meeting",          (7.5, 6.8),  "Root cause: null pointer"),
        ("Dev",      "meeting",          (9.0, 6.5),  "Hotfix ready in 10 min"),
        ("Manager",  "meeting",          (8.3, 5.5),  "Notify stakeholders?"),
        ("Planner",  "desk",             None,        "Hotfix approved. Deploy!"),
        ("Dev",      "desk",             None,        "Deploying fix... Done!"),
        ("Analyst",  "desk",             None,        "Bug resolved. Monitoring..."),
    ],
    "Data Analysis": [
        ("Planner",  "desk",             None,        "Task: Q4 data report"),
        ("Analyst",  "office_fetching",  (10.5, 3.5), "Fetching Q4 datasets..."),
        ("Analyst",  "desk",             None,        "Running statistical models..."),
        ("Dev",      "desk",             None,        "Building data pipeline..."),
        ("Analyst",  "desk",             None,        "Anomaly found in dataset!"),
        ("Planner",  "desk",             None,        "Investigating anomaly..."),
        ("Analyst",  "office_fetching",  (10.5, 2.8), "Cross-referencing archives..."),
        ("Dev",      "desk",             None,        "Visualization ready!"),
        ("Manager",  "meeting",          (8.3, 6.5),  "Review report together"),
        ("Analyst",  "meeting",          (7.5, 6.8),  "Revenue up 23%!"),
        ("Planner",  "desk",             None,        "Report sent to board!"),
    ],
    "New AI Feature": [
        ("Planner",  "desk",             None,        "Brainstorming AI features..."),
        ("Designer", "office_fetching",  (10.5, 3.0), "Getting design specs..."),
        ("Dev",      "desk",             None,        "Setting up ML pipeline..."),
        ("Analyst",  "desk",             None,        "Training data prep..."),
        ("Designer", "desk",             None,        "Designing AI interface..."),
        ("Planner",  "meeting",          (8.5, 5.8),  "Feature review meeting"),
        ("Dev",      "meeting",          (9.0, 6.5),  "Model accuracy: 94%!"),
        ("Analyst",  "meeting",          (7.5, 6.8),  "Bias check: passed!"),
        ("Designer", "meeting",          (7.8, 5.5),  "UX score: excellent!"),
        ("Planner",  "desk",             None,        "Greenlit! Ship it!"),
        ("Dev",      "desk",             None,        "AI feature deployed!"),
    ],
}

RANDOM_EVENTS = [
    ("Analyst",  "Server spiked to 100%!"),
    ("Dev",      "Dependency update broke build!"),
    ("Manager",  "Client wants demo NOW!"),
    ("Planner",  "Switching priorities..."),
    ("Designer", "Brand guidelines changed!"),
    ("Dev",      "Found performance bottleneck!"),
    ("Analyst",  "New data arrived!"),
    ("Manager",  "Budget cut by 20%!"),
    ("Planner",  "Competitor launched feature!"),
]

# ── Main Simulation ────────────────────────────────────────────────────────────
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("AI Office Simulation")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("Arial", 22, bold=True)
    font_med   = pygame.font.SysFont("Arial", 16)
    font_small = pygame.font.SysFont("Arial", 13)
    font_tiny  = pygame.font.SysFont("Arial", 11)

    desk_home = {
        "Planner":  (2.9, 2.5),
        "Analyst":  (5.9, 2.5),
        "Dev":      (8.9, 2.5),
        "Manager":  (2.9, 5.5),
        "Designer": (5.9, 5.5),
    }

    agents = [
        Agent("Lexi",    "Planner",  2.9, 2.5, desk_home["Planner"],
              AGENT_COLORS["Planner"],  AGENT_COLORS_DARK["Planner"]),
        Agent("Axel",    "Analyst",  5.9, 2.5, desk_home["Analyst"],
              AGENT_COLORS["Analyst"],  AGENT_COLORS_DARK["Analyst"]),
        Agent("Dev-3000","Dev",      8.9, 2.5, desk_home["Dev"],
              AGENT_COLORS["Dev"],      AGENT_COLORS_DARK["Dev"]),
        Agent("Marco",   "Manager",  2.9, 5.5, desk_home["Manager"],
              AGENT_COLORS["Manager"],  AGENT_COLORS_DARK["Manager"]),
        Agent("Aria",    "Designer", 5.9, 5.5, desk_home["Designer"],
              AGENT_COLORS["Designer"], AGENT_COLORS_DARK["Designer"]),
    ]
    agent_map = {a.role: a for a in agents}

    scenario_names = list(SCENARIOS.keys())
    current_scenario = 0
    step_index = 0
    step_timer = 0.0
    step_delay = 2.8
    running_scenario = False
    paused = False
    log = []
    random_event_timer = random.uniform(15, 25)
    scene_complete = False

    def start_scenario(idx):
        nonlocal step_index, step_timer, running_scenario, scene_complete
        # Reset agents
        for a in agents:
            a.state = AgentState.IDLE
            a.bubble = None
            a.gx, a.gy = a.desk
        step_index = 0
        step_timer = 0
        running_scenario = True
        scene_complete = False
        log.append(f"▶ Starting: {scenario_names[idx]}")

    def execute_step(step):
        role, action, pos, text = step
        a = agent_map.get(role)
        if not a:
            return
        a.say(text, 3.2)
        log.append(f"[{role}] {text}")
        if len(log) > 12:
            log.pop(0)

        if action == "desk":
            hx, hy = a.desk
            a.set_target(hx, hy)
            a.state = AgentState.WORKING
        elif action == "meeting":
            if pos:
                a.set_target(pos[0], pos[1])
                a.state = AgentState.MEETING
        elif action == "office_fetching":
            if pos:
                a.set_target(pos[0], pos[1])
                a.state = AgentState.FETCHING
        elif action == "coffee":
            a.set_target(10.4, 7.4)
            a.state = AgentState.COFFEE
        a.busy_timer = step_delay + 1

    def trigger_random_event():
        role, msg = random.choice(RANDOM_EVENTS)
        a = agent_map.get(role)
        if a:
            a.say("⚡ " + msg, 4.0)
            log.append(f"[RANDOM] {msg}")
            if len(log) > 12:
                log.pop(0)

    # Button rects
    btn_h = 36
    btn_y = HEIGHT - 55
    btn_prev = pygame.Rect(20, btn_y, 100, btn_h)
    btn_play = pygame.Rect(130, btn_y, 120, btn_h)
    btn_pause = pygame.Rect(260, btn_y, 100, btn_h)
    btn_next = pygame.Rect(370, btn_y, 100, btn_h)
    btn_rand = pygame.Rect(490, btn_y, 150, btn_h)

    def draw_button(surf, rect, text, active=False, hover=False):
        c = (100, 160, 240) if active else ((180, 200, 230) if hover else (200, 210, 225))
        pygame.draw.rect(surf, c, rect, border_radius=8)
        pygame.draw.rect(surf, (80, 100, 140), rect, 2, border_radius=8)
        tx = font_med.render(text, True, (30, 30, 60))
        surf.blit(tx, (rect.centerx - tx.get_width()//2,
                       rect.centery - tx.get_height()//2))

    running = True
    dt = 0.0

    while running:
        dt = clock.tick(FPS) / 1000.0
        mx, my = pygame.mouse.get_pos()

        # ── Events ─────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not running_scenario:
                        start_scenario(current_scenario)
                    else:
                        paused = not paused
                elif event.key == pygame.K_LEFT:
                    current_scenario = (current_scenario - 1) % len(scenario_names)
                    running_scenario = False
                elif event.key == pygame.K_RIGHT:
                    current_scenario = (current_scenario + 1) % len(scenario_names)
                    running_scenario = False
                elif event.key == pygame.K_r:
                    trigger_random_event()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if btn_prev.collidepoint(mx, my):
                    current_scenario = (current_scenario - 1) % len(scenario_names)
                    running_scenario = False
                elif btn_play.collidepoint(mx, my):
                    start_scenario(current_scenario)
                    paused = False
                elif btn_pause.collidepoint(mx, my):
                    paused = not paused
                elif btn_next.collidepoint(mx, my):
                    current_scenario = (current_scenario + 1) % len(scenario_names)
                    running_scenario = False
                elif btn_rand.collidepoint(mx, my):
                    trigger_random_event()

        # ── Update ──────────────────────────────────────────────────────────────
        if not paused:
            for a in agents:
                a.update(dt)

            random_event_timer -= dt
            if random_event_timer <= 0:
                if running_scenario:
                    trigger_random_event()
                random_event_timer = random.uniform(18, 30)

            if running_scenario and not scene_complete:
                step_timer += dt
                steps = SCENARIOS[scenario_names[current_scenario]]
                if step_timer >= step_delay:
                    step_timer = 0
                    if step_index < len(steps):
                        execute_step(steps[step_index])
                        step_index += 1
                    else:
                        scene_complete = True
                        running_scenario = False
                        log.append(f"✓ Scenario complete!")

        # ── Draw ────────────────────────────────────────────────────────────────
        screen.fill(C_BG)
        draw_office(screen)

        # Draw agents (sorted by y for pseudo-depth)
        for a in sorted(agents, key=lambda x: x.gx + x.gy):
            a.draw(screen)

        # Draw bubbles on top
        for a in agents:
            a.draw_bubble(screen, font_small)

        # ── HUD panel (right) ──────────────────────────────────────────────────
        panel_x = WIDTH - 260
        panel = pygame.Surface((250, HEIGHT - 20), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 180))
        pygame.draw.rect(panel, (100, 120, 160, 200), panel.get_rect(), 2, border_radius=10)
        screen.blit(panel, (panel_x, 10))

        # Title
        t = font_title.render("AI Office Sim", True, (40, 60, 120))
        screen.blit(t, (panel_x + 15, 22))

        # Scenario label
        y = 55
        screen.blit(font_med.render("Scenario:", True, (80, 80, 100)), (panel_x + 15, y))
        y += 22
        sn = font_med.render(scenario_names[current_scenario], True, (30, 100, 180))
        screen.blit(sn, (panel_x + 15, y))

        # Progress bar
        y += 28
        steps = SCENARIOS[scenario_names[current_scenario]]
        prog = step_index / len(steps) if len(steps) > 0 else 0
        prog_rect = pygame.Rect(panel_x + 15, y, 220, 10)
        pygame.draw.rect(screen, (200, 210, 230), prog_rect, border_radius=5)
        pygame.draw.rect(screen, (80, 160, 220),
                         pygame.Rect(panel_x + 15, y, int(220 * prog), 10), border_radius=5)
        y += 18

        # Agents status
        screen.blit(font_med.render("Agents:", True, (80, 80, 100)), (panel_x + 15, y))
        y += 22
        for a in agents:
            col = a.color
            pygame.draw.circle(screen, col, (panel_x + 22, y + 8), 7)
            pygame.draw.circle(screen, a.color_dark, (panel_x + 22, y + 8), 7, 1)
            status = a.state.value.upper()
            txt = font_tiny.render(f"{a.name} ({a.role}) – {status}", True, (40, 40, 60))
            screen.blit(txt, (panel_x + 34, y + 2))
            y += 20

        # Log
        y += 8
        screen.blit(font_med.render("Event Log:", True, (80, 80, 100)), (panel_x + 15, y))
        y += 22
        for line in log[-10:]:
            wrapped = []
            words = line.split()
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if font_tiny.size(test)[0] > 220:
                    wrapped.append(cur)
                    cur = w
                else:
                    cur = test
            if cur:
                wrapped.append(cur)
            for wl in wrapped:
                lt = font_tiny.render(wl, True, (50, 60, 80))
                screen.blit(lt, (panel_x + 15, y))
                y += 15
                if y > HEIGHT - 100:
                    break

        # ── Status bar ─────────────────────────────────────────────────────────
        bar = pygame.Surface((WIDTH, 70), pygame.SRCALPHA)
        bar.fill((230, 225, 215, 220))
        screen.blit(bar, (0, HEIGHT - 70))

        # Buttons
        draw_button(screen, btn_prev, "◀ Prev", hover=btn_prev.collidepoint(mx, my))
        draw_button(screen, btn_play, "▶ Play", active=running_scenario and not paused,
                    hover=btn_play.collidepoint(mx, my))
        draw_button(screen, btn_pause, "⏸ Pause" if not paused else "▶ Resume",
                    active=paused, hover=btn_pause.collidepoint(mx, my))
        draw_button(screen, btn_next, "Next ▶", hover=btn_next.collidepoint(mx, my))
        draw_button(screen, btn_rand, "⚡ Random Event", hover=btn_rand.collidepoint(mx, my))

        # Hotkeys hint
        hint = font_tiny.render("SPACE: Play/Pause | ←→: Scenario | R: Random Event | ESC: Quit",
                                 True, (100, 100, 120))
        screen.blit(hint, (panel_x - 400, HEIGHT - 20))

        # Scene complete banner
        if scene_complete:
            bw, bh = 360, 50
            bx, by = WIDTH // 2 - bw // 2 - 130, HEIGHT // 2 - bh // 2
            banner = pygame.Surface((bw, bh), pygame.SRCALPHA)
            banner.fill((80, 200, 120, 220))
            pygame.draw.rect(banner, (40, 140, 80, 255), banner.get_rect(), 2, border_radius=12)
            screen.blit(banner, (bx, by))
            ct = font_title.render("✓ Scenario Complete!", True, C_WHITE)
            screen.blit(ct, (bx + bw//2 - ct.get_width()//2, by + bh//2 - ct.get_height()//2))

        # Paused overlay
        if paused:
            ov = pygame.Surface((120, 40), pygame.SRCALPHA)
            ov.fill((40, 40, 80, 180))
            screen.blit(ov, (20, 20))
            screen.blit(font_med.render("⏸ PAUSED", True, C_WHITE), (28, 28))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
