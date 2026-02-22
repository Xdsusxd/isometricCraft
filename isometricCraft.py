import sys
import math
import ctypes

import pygame
from pygame.locals import *
import numpy as np

try:
    from OpenGL.GL import *
    from OpenGL.GL.shaders import compileProgram, compileShader
    HAS_GL = True
except ImportError:
    HAS_GL = False
    print("PyOpenGL no encontrado efectos visuales desactivados.")
    print("intalar opengl")

W, H   = 1280, 720
FPS    = 60

GX, GY, GZ = 20, 20, 12

TW = 48
TH = 24
BH = TH

EMPTY = 0
GRASS, DIRT, STONE, WOOD, WATER, SAND, BRICK, SNOW, LEAF = range(1, 10)

PALETTE = [GRASS, DIRT, STONE, WOOD, WATER, SAND, BRICK, SNOW, LEAF]
NAMES   = ["", "Hierba", "Tierra", "Piedra", "Madera",
           "Agua", "Arena", "Ladrillo", "Nieve", "Hoja"]

COL = {
    GRASS: [(106,180, 76), ( 82,140, 58), ( 65,110, 46)],
    DIRT:  [(150,100, 60), (120, 80, 48), ( 95, 63, 38)],
    STONE: [(160,160,160), (130,130,130), (100,100,100)],
    WOOD:  [(180,140, 80), (140,110, 60), (110, 85, 46)],
    WATER: [( 80,140,220), ( 60,110,180), ( 45, 85,140)],
    SAND:  [(220,200,140), (180,165,115), (140,128, 89)],
    BRICK: [(180, 90, 70), (145, 72, 56), (115, 57, 44)],
    SNOW:  [(240,245,255), (200,210,225), (160,170,190)],
    LEAF:  [( 60,160, 50), ( 45,125, 38), ( 35, 98, 30)],
}

VERT_SRC = """
#version 330 core
layout(location=0) in vec2 aPos;
layout(location=1) in vec2 aUV;
out vec2 vUV;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vUV = aUV;
}
"""

FRAG_SRC = """
#version 330 core
in vec2 vUV;
out vec4 fragColor;
uniform sampler2D uTex;
uniform float uTime;

void main() {
    vec2 uv = vUV;

    vec2 cc = uv * 2.0 - 1.0;
    float d  = dot(cc, cc);
    cc      *= 1.0 + d * 0.016;
    vec2 distUV = clamp((cc + 1.0) * 0.5, 0.001, 0.999);

    vec2 pRes   = vec2(640.0, 360.0);
    vec2 pixUV  = (floor(distUV * pRes) + 0.5) / pRes;
    vec4 col    = texture(uTex, pixUV);

    float vign  = 1.0 - d * 0.40;
    col.rgb    *= clamp(vign, 0.0, 1.0);

    float scan  = 0.965 + 0.035 * sin(uv.y * 720.0 * 3.14159265);
    col.rgb    *= scan;

    col.rgb = pow(max(col.rgb, 0.0), vec3(0.93, 1.00, 1.07));

    col.rgb = clamp((col.rgb - 0.5) * 1.12 + 0.5, 0.0, 1.0);

    float ca = d * 0.004;
    float r  = texture(uTex, pixUV + vec2( ca, 0.0)).r;
    float b2 = texture(uTex, pixUV - vec2( ca, 0.0)).b;
    col.r    = mix(col.r, r,  0.45);
    col.b    = mix(col.b, b2, 0.45);

    fragColor = col;
}
"""

class Game:

    def __init__(self):
        pygame.init()
        if HAS_GL:
            pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
        else:
            pygame.display.set_mode((W, H))
        pygame.display.set_caption("minecraft isometrico creado por el sus")

        if HAS_GL:
            self._gl_init()

        self.surf       = pygame.Surface((W, H))
        self.ghost_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.clock      = pygame.time.Clock()
        self.font_sm    = pygame.font.SysFont("monospace", 13, bold=True)
        self.font_md    = pygame.font.SysFont("monospace", 17, bold=True)

        self.world = [[[EMPTY]*GX for _ in range(GY)] for _ in range(GZ)]
        self._build_world()

        self.cam_x   = W // 2
        self.cam_y   = H // 3
        self.cam_rot = 0

        self.pal_idx  = 0
        self.sel_blk  = GRASS
        self.hov_blk  = None
        self.place_at = None

        self.sky = self._make_sky()
        self.t   = 0.0

    def _build_world(self):
        for y in range(GY):
            for x in range(GX):
                self.world[0][y][x] = GRASS

        for x, y in [(3,3),(4,3),(3,4),(4,4),(12,10),(13,10),(12,11)]:
            if 0<=x<GX and 0<=y<GY:
                self.world[0][y][x] = DIRT
                self.world[1][y][x] = DIRT

        for x, y in [(15,5),(16,5),(15,6),(16,6)]:
            for z in range(3):
                if 0<=x<GX and 0<=y<GY: self.world[z][y][x] = STONE
        for x, y in [(15,5),(16,5)]:
            if 0<=x<GX and 0<=y<GY: self.world[3][y][x] = STONE

        for x in range(7, 11):
            for y in range(7, 11):
                self.world[0][y][x] = WOOD
                self.world[1][y][x] = WOOD

        for x in range(2, 6):
            for y in range(12, 16):
                if 0<=x<GX and 0<=y<GY:
                    self.world[0][y][x] = WATER

        for x, y in [(9,3)]:
            for z in range(2): self.world[z][y][x] = WOOD
            for dx in range(-1,2):
                for dy in range(-1,2):
                    nx, ny = x+dx, y+dy
                    if 0<=nx<GX and 0<=ny<GY:
                        self.world[2][ny][nx] = LEAF
            self.world[3][y][x] = LEAF

    def _make_sky(self):
        sky = pygame.Surface((W, H))
        for yy in range(H):
            frac = yy / H
            r = int(15 + frac * 35)
            g = int(18 + frac * 30)
            b = int(42 + frac * 55)
            pygame.draw.line(sky, (r, g, b), (0, yy), (W, yy))
        return sky

    def _gl_init(self):
        self.prog = compileProgram(
            compileShader(VERT_SRC, GL_VERTEX_SHADER),
            compileShader(FRAG_SRC, GL_FRAGMENT_SHADER),
        )
        quad = np.array([
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
             1.0,  1.0,  1.0, 1.0,
            -1.0,  1.0,  0.0, 1.0,
        ], dtype=np.float32)
        idx = np.array([0,1,2, 2,3,0], dtype=np.uint32)

        self.vao = glGenVertexArrays(1)
        vbo, ebo = glGenBuffers(2)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL_STATIC_DRAW)
        stride = 4 * quad.itemsize
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

        self.tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, H, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, None)

    def _rotate(self, gx, gy):
        r = self.cam_rot
        if   r == 0: return gx,            gy
        elif r == 1: return GY - 1 - gy,  gx
        elif r == 2: return GX - 1 - gx,  GY - 1 - gy
        else:        return gy,             GX - 1 - gx

    def _unrotate(self, rx, ry):
        r = self.cam_rot
        if   r == 0: return rx,             ry
        elif r == 1: return ry,             GY - 1 - rx
        elif r == 2: return GX - 1 - rx,   GY - 1 - ry
        else:        return GX - 1 - ry,   rx

    def w2s(self, gx, gy, gz):
        rx, ry = self._rotate(gx, gy)
        return (self.cam_x + (rx - ry) * TW // 2,
                self.cam_y + (rx + ry) * TH // 2 - gz * BH)

    def s2w(self, sx, sy, gz):
        dx = sx - self.cam_x
        dy = sy - self.cam_y + gz * BH
        rs = 2 * dy / TH
        rd = 2 * dx / TW
        rx = int(math.floor((rs + rd) / 2))
        ry = int(math.floor((rs - rd) / 2))
        return self._unrotate(rx, ry)

    def _render_order(self):
        order = []
        for gz in range(GZ):
            for d in range(GX + GY - 1):
                for rx in range(max(0, d - GY + 1), min(GX, d + 1)):
                    ry = d - rx
                    if 0 <= ry < GY:
                        gx, gy = self._unrotate(rx, ry)
                        if 0 <= gx < GX and 0 <= gy < GY:
                            order.append((gx, gy, gz))
        return order

    def _draw_cube(self, surf, gx, gy, gz, blk, hl=False, alpha=255):
        sx, sy = self.w2s(gx, gy, gz)
        top, lft, rgt = [tuple(c) for c in COL[blk]]

        if blk == WATER:
            w = int(14 * math.sin(self.t * 2.8 + gx * 0.5 + gy * 0.5))
            top = (top[0], min(255, top[1] + w), min(255, top[2] + w * 2))
            lft = (lft[0], min(255, lft[1] + w//2), lft[2])

        if hl:
            top = tuple(min(255, c + 75) for c in top)
            lft = tuple(min(255, c + 55) for c in lft)
            rgt = tuple(min(255, c + 55) for c in rgt)

        hw, hh = TW // 2, TH // 2

        T = [(sx,      sy),
             (sx + hw, sy + hh),
             (sx,      sy + TH),
             (sx - hw, sy + hh)]
        L = [(sx - hw, sy + hh),
             (sx,      sy + TH),
             (sx,      sy + TH + BH),
             (sx - hw, sy + hh + BH)]
        R = [(sx + hw, sy + hh),
             (sx,      sy + TH),
             (sx,      sy + TH + BH),
             (sx + hw, sy + hh + BH)]

        if alpha < 255:
            pygame.draw.polygon(surf, (*lft, alpha), L)
            pygame.draw.polygon(surf, (*rgt, alpha), R)
            pygame.draw.polygon(surf, (*top, alpha), T)
            pygame.draw.lines (surf, (255, 255, 255, 200), True, T, 2)
            return

        pygame.draw.polygon(surf, lft, L)
        pygame.draw.polygon(surf, rgt, R)
        pygame.draw.polygon(surf, top, T)

        oc = (255, 255, 255) if hl else (0, 0, 0)
        pygame.draw.lines(surf, oc, True, T, 1)
        pygame.draw.lines(surf, oc, True, L, 1)
        pygame.draw.lines(surf, oc, True, R, 1)

        if blk not in (WATER, SNOW, LEAF):
            dim = tuple(max(0, c - 30) for c in top)
            pygame.draw.line(surf, dim, T[0], T[2], 1)
            pygame.draw.line(surf, dim, T[1], T[3], 1)

        if blk == BRICK:
            mc = tuple(max(0, c - 20) for c in lft)
            y_mid = (L[0][1] + L[3][1]) // 2
            pygame.draw.line(surf, mc, L[0], L[3], 1)
            pygame.draw.line(surf, mc, (L[0][0]+8, L[0][1]), (L[3][0]+8, L[3][1]), 1)
            mc2 = tuple(max(0, c - 20) for c in rgt)
            pygame.draw.line(surf, mc2, R[0], R[3], 1)
            pygame.draw.line(surf, mc2, (R[0][0]-8, R[0][1]), (R[3][0]-8, R[3][1]), 1)

        if blk == WOOD:
            vein = tuple(max(0, c - 18) for c in lft)
            x_mid = (L[0][0] + L[1][0]) // 2
            pygame.draw.line(surf, vein,
                             ((L[0][0]+L[1][0])//2, L[0][1]),
                             ((L[3][0]+L[2][0])//2, L[3][1]), 1)

    def _hit_test(self, mx, my):
        for gz in range(GZ - 1, -1, -1):
            gx, gy = self.s2w(mx, my, gz)
            if 0 <= gx < GX and 0 <= gy < GY and self.world[gz][gy][gx] != EMPTY:
                pz = gz + 1
                return (gx, gy, gz), ((gx, gy, pz) if pz < GZ else None)
        gx, gy = self.s2w(mx, my, 0)
        if 0 <= gx < GX and 0 <= gy < GY:
            return None, (gx, gy, 0)
        return None, None

    def _draw_hud(self):
        s = self.surf
        n, pw, ph = len(PALETTE), len(PALETTE) * 58 + 18, 76
        px, py = (W - pw) // 2, H - ph - 10

        bar = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bar.fill((8, 10, 20, 175))
        s.blit(bar, (px, py))
        pygame.draw.rect(s, (70, 80, 110), (px, py, pw, ph), 2)

        for i, blk in enumerate(PALETTE):
            bx = px + 9 + i * 58
            by = py + 9
            c  = COL[blk]

            pygame.draw.rect(s, c[0], (bx + 4,  by + 2,  48, 20))
            pygame.draw.rect(s, c[1], (bx + 4,  by + 22, 24, 16))
            pygame.draw.rect(s, c[2], (bx + 28, by + 22, 24, 16))
            pygame.draw.rect(s, (0, 0, 0), (bx + 4, by + 2, 48, 36), 1)

            if i == self.pal_idx:
                pygame.draw.rect(s, (255, 215, 35), (bx + 1, by - 1, 54, 60), 3)

            lbl = self.font_sm.render(NAMES[blk][:6], True, (210, 215, 230))
            s.blit(lbl, (bx + (54 - lbl.get_width()) // 2, by + 42))

        hints = [
            " LMB:Colocar  RMB:Borrar ",
            " WASD/↑↓←→:Mover  Q/E:Rotar ",
            " 1-9/Rueda:Bloque ",
        ]
        for i, txt in enumerate(hints):
            t  = self.font_sm.render(txt, True, (200, 210, 230))
            bg = pygame.Surface((t.get_width() + 8, t.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            s.blit(bg, (6, 6 + i * 18))
            s.blit(t,  (10, 8 + i * 18))

        label = f"▶ {NAMES[self.sel_blk]}"
        t = self.font_md.render(label, True, (255, 218, 45))
        bg2 = pygame.Surface((t.get_width()+10, t.get_height()+4), pygame.SRCALPHA)
        bg2.fill((0,0,0,140))
        s.blit(bg2, (W - t.get_width() - 18, 8))
        s.blit(t,   (W - t.get_width() - 13, 10))

        dirs = ["Norte ↑", "Este →", "Sur ↓", "Oeste ←"]
        t2 = self.font_sm.render(f"Cámara: {dirs[self.cam_rot]}", True, (150, 200, 255))
        bg3 = pygame.Surface((t2.get_width()+10, t2.get_height()+4), pygame.SRCALPHA)
        bg3.fill((0,0,0,140))
        s.blit(bg3, (W - t2.get_width() - 18, 34))
        s.blit(t2,  (W - t2.get_width() - 13, 36))

    def _gl_pass(self):
        raw = pygame.image.tostring(self.surf, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self.tex_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W, H,
                        GL_RGBA, GL_UNSIGNED_BYTE, raw)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.prog)
        glUniform1i(glGetUniformLocation(self.prog, "uTex"),  0)
        glUniform1f(glGetUniformLocation(self.prog, "uTime"), self.t)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.tex_id)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def run(self):
        while True:
            dt         = self.clock.tick(FPS) / 1000.0
            self.t    += dt
            mx, my     = pygame.mouse.get_pos()
            self.hov_blk, self.place_at = self._hit_test(mx, my)

            for ev in pygame.event.get():
                if ev.type == QUIT:
                    pygame.quit(); sys.exit()
                elif ev.type == KEYDOWN:
                    if ev.key == K_ESCAPE:
                        pygame.quit(); sys.exit()
                    elif ev.key == K_q:
                        self.cam_rot = (self.cam_rot - 1) % 4
                    elif ev.key == K_e:
                        self.cam_rot = (self.cam_rot + 1) % 4
                    else:
                        for i, k in enumerate([K_1,K_2,K_3,K_4,K_5,K_6,K_7,K_8,K_9]):
                            if ev.key == k and i < len(PALETTE):
                                self.pal_idx = i
                                self.sel_blk = PALETTE[i]
                elif ev.type == MOUSEWHEEL:
                    d = -1 if ev.y > 0 else 1
                    self.pal_idx = (self.pal_idx + d) % len(PALETTE)
                    self.sel_blk = PALETTE[self.pal_idx]
                elif ev.type == MOUSEBUTTONDOWN:
                    if ev.button == 1 and self.place_at:
                        px2, py2, pz2 = self.place_at
                        if 0<=px2<GX and 0<=py2<GY and 0<=pz2<GZ:
                            self.world[pz2][py2][px2] = self.sel_blk
                    elif ev.button == 3 and self.hov_blk:
                        hx, hy, hz = self.hov_blk
                        self.world[hz][hy][hx] = EMPTY

            spd  = 7
            keys = pygame.key.get_pressed()
            if keys[K_w] or keys[K_UP]:    self.cam_y -= spd
            if keys[K_s] or keys[K_DOWN]:  self.cam_y += spd
            if keys[K_a] or keys[K_LEFT]:  self.cam_x -= spd
            if keys[K_d] or keys[K_RIGHT]: self.cam_x += spd

            self.surf.blit(self.sky, (0, 0))

            for gy in range(GY):
                for gx in range(GX):
                    sx, sy = self.w2s(gx, gy, 0)
                    hw = TW // 2
                    hh = TH // 2
                    pts = [(sx, sy), (sx+hw, sy+hh), (sx, sy+TH), (sx-hw, sy+hh)]
                    col = (20, 24, 40) if (gx + gy) % 2 == 0 else (24, 28, 48)
                    pygame.draw.polygon(self.surf, col, pts)
                    pygame.draw.lines (self.surf, (36, 42, 65), True, pts, 1)

            for gx, gy, gz in self._render_order():
                blk = self.world[gz][gy][gx]
                if blk == EMPTY:
                    continue
                hl = (self.place_at is not None and
                      self.place_at[0] == gx and
                      self.place_at[1] == gy and
                      self.place_at[2] == gz + 1)
                self._draw_cube(self.surf, gx, gy, gz, blk, hl=hl)

            if self.place_at:
                px2, py2, pz2 = self.place_at
                if 0 <= px2 < GX and 0 <= py2 < GY and 0 <= pz2 < GZ:
                    self.ghost_surf.fill((0, 0, 0, 0))
                    self._draw_cube(self.ghost_surf, px2, py2, pz2,
                                    self.sel_blk, alpha=135)
                    self.surf.blit(self.ghost_surf, (0, 0))

            self._draw_hud()

            if HAS_GL:
                self._gl_pass()
            else:
                pygame.display.get_surface().blit(self.surf, (0, 0))
            pygame.display.flip()

if __name__ == "__main__":
    Game().run()