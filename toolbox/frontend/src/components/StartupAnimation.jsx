import { useEffect, useState, useRef } from 'react'

const GOOGLE_FONTS =
  'https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&family=Caveat:wght@600;700&family=Quicksand:wght@500;600&family=DM+Serif+Display&display=swap'

const THEME_SUBTITLES = {
  hofblick: 'Alles im Blick',
  koppel: 'Dein Platz für Tier & Kind',
  hufspur: 'Jede Einheit hinterlässt Spuren',
  stallgefluester: 'Geschichten vom Hof',
}

const KEYFRAMES = `
@import url('${GOOGLE_FONTS}');

@keyframes sa-rise { from { transform: translateY(60px) scale(0.5); opacity: 0; } to { transform: translateY(0) scale(1); opacity: 1; } }
@keyframes sa-slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
@keyframes sa-bounceIn { 0% { transform: scale(0) translateY(30px); opacity: 0; } 60% { transform: scale(1.15) translateY(-6px); opacity: 1; } 80% { transform: scale(0.95) translateY(2px); } 100% { transform: scale(1) translateY(0); opacity: 1; } }
@keyframes sa-fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
@keyframes sa-bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes sa-sway { 0%,100% { transform: rotate(-6deg); } 50% { transform: rotate(6deg); } }
@keyframes sa-pulse { 0%,100% { opacity: 0.4; transform: scale(0.9); } 50% { opacity: 1; transform: scale(1.1); } }
@keyframes sa-fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes sa-orbit { from { transform: rotate(0deg) translateX(80px) rotate(0deg); } to { transform: rotate(360deg) translateX(80px) rotate(-360deg); } }
@keyframes sa-scaleIn { from { transform: scale(0); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@keyframes sa-bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
@keyframes sa-twinkle { 0%,100% { opacity: 0.2; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
@keyframes sa-float { 0%,100% { transform: translateY(0); opacity: 1; } 100% { transform: translateY(-40px); opacity: 0; } }
@keyframes sa-expand { from { width: 0; } to { width: 120px; } }
@keyframes sa-stepIn { from { opacity: 0; transform: scale(0.5) rotate(-20deg); } to { opacity: 1; transform: scale(1) rotate(0deg); } }
@keyframes sa-fadeOut { from { opacity: 1; } to { opacity: 0; } }
`

/* ── Hofblick ─────────────────────────────────────────────────── */
function HofblickTheme({ appName, subtitle }) {
  const [grass, setGrass] = useState([])
  useEffect(() => {
    setGrass(Array.from({ length: 40 }, (_, i) => ({
      left: `${(i / 40) * 100 + Math.random() * 2}%`,
      height: `${14 + Math.random() * 14}px`,
      delay: `${Math.random() * 2}s`,
      duration: `${1.2 + Math.random() * 0.8}s`,
    })))
  }, [])

  const sub = subtitle || THEME_SUBTITLES.hofblick

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: 'linear-gradient(180deg, #fff8e1 0%, #f9f3d0 30%, #c8e6c9 70%, #81c784 100%)',
    }}>
      {/* Sun */}
      <div style={{
        position: 'absolute', top: '12%', left: '50%', transform: 'translateX(-50%)',
        width: 90, height: 90, borderRadius: '50%',
        background: 'radial-gradient(circle, #ffe082 60%, #ffb300 100%)',
        boxShadow: '0 0 60px 20px rgba(255,193,7,0.4)',
        animation: 'sa-rise 1s cubic-bezier(.22,1,.36,1) 0.2s both',
      }} />

      {/* Hills */}
      {[
        { color: '#388e3c', w: '160%', h: '42%', b: '18%', delay: '0.5s' },
        { color: '#43a047', w: '130%', h: '36%', b: '14%', delay: '0.7s' },
        { color: '#66bb6a', w: '110%', h: '30%', b: '10%', delay: '0.9s' },
      ].map((hill, i) => (
        <div key={i} style={{
          position: 'absolute', bottom: hill.b, left: '-5%',
          width: hill.w, height: hill.h,
          background: hill.color,
          borderRadius: '50% 50% 0 0',
          animation: `sa-slideUp 0.7s cubic-bezier(.22,1,.36,1) ${hill.delay} both`,
        }} />
      ))}

      {/* Animals on hills */}
      {['🐴', '🫏', '🐎', '🐴'].map((e, i) => (
        <div key={i} style={{
          position: 'absolute',
          bottom: `${20 + i * 3}%`,
          left: `${15 + i * 20}%`,
          fontSize: 28,
          animation: `sa-bob 2s ease-in-out ${0.3 * i}s infinite`,
          zIndex: 4,
        }}>{e}</div>
      ))}

      {/* Grass blades */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 40, zIndex: 5 }}>
        {grass.map((g, i) => (
          <div key={i} style={{
            position: 'absolute', bottom: 0, left: g.left,
            width: 3, height: g.height, background: '#2e7d32',
            borderRadius: '2px 2px 0 0', transformOrigin: 'bottom center',
            animation: `sa-sway ${g.duration} ease-in-out ${g.delay} infinite`,
          }} />
        ))}
      </div>

      {/* App name */}
      <div style={{
        position: 'absolute', top: '36%', left: 0, right: 0, textAlign: 'center', zIndex: 10,
      }}>
        <div style={{
          fontFamily: '"Baloo 2", sans-serif', fontWeight: 800,
          fontSize: 'clamp(48px, 10vw, 72px)', color: '#1b5e20', lineHeight: 1,
          animation: 'sa-bounceIn 0.8s cubic-bezier(.22,1,.36,1) 0.8s both',
        }}>{appName}</div>
        <div style={{
          fontFamily: '"Caveat", cursive', fontWeight: 600,
          fontSize: 'clamp(18px, 4vw, 26px)', color: '#558b2f', marginTop: 6,
          animation: 'sa-fadeUp 0.6s ease 1.2s both',
        }}>{sub}</div>
      </div>

      {/* Loader */}
      <div style={{
        position: 'absolute', bottom: '6%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', gap: 12, zIndex: 10,
        animation: 'sa-fadeIn 0.4s ease 1.6s both',
      }}>
        {['🐾', '🐾', '🐾', '🐾'].map((e, i) => (
          <span key={i} style={{
            fontSize: 20,
            animation: `sa-pulse 1s ease-in-out ${i * 0.2}s infinite`,
          }}>{e}</span>
        ))}
      </div>
    </div>
  )
}

/* ── Koppel ───────────────────────────────────────────────────── */
function KoppelTheme({ appName, subtitle }) {
  const sub = subtitle || THEME_SUBTITLES.koppel
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: '#f0f7ec',
    }}>
      {/* Background circles */}
      {[
        { size: 320, top: '-10%', left: '-8%', color: 'rgba(102,187,106,0.25)', delay: '0s' },
        { size: 260, top: '30%', right: '-10%', color: 'rgba(255,152,0,0.15)', delay: '0.2s' },
        { size: 180, bottom: '5%', left: '20%', color: 'rgba(129,199,132,0.3)', delay: '0.4s' },
      ].map((c, i) => (
        <div key={i} style={{
          position: 'absolute', width: c.size, height: c.size,
          borderRadius: '50%', background: c.color,
          top: c.top, left: c.left, right: c.right, bottom: c.bottom,
          animation: `sa-scaleIn 0.8s cubic-bezier(.22,1,.36,1) ${c.delay} both`,
        }} />
      ))}

      {/* Fence */}
      <div style={{
        position: 'absolute', bottom: '18%', left: 0, right: 0, height: 60, zIndex: 3,
        animation: 'sa-fadeUp 0.6s ease 0.5s both',
      }}>
        {Array.from({ length: 12 }, (_, i) => (
          <div key={i} style={{
            position: 'absolute', left: `${i * 9 - 2}%`, bottom: 0,
            width: 10, height: 52, background: '#8d6e63', borderRadius: 4,
          }} />
        ))}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 14, height: 8,
          background: '#795548', borderRadius: 4,
        }} />
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 34, height: 8,
          background: '#795548', borderRadius: 4,
        }} />
      </div>

      {/* Central circle */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -54%)',
        width: 160, height: 160, borderRadius: '50%',
        background: '#388e3c',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 56, zIndex: 5,
        animation: 'sa-scaleIn 0.6s cubic-bezier(.22,1,.36,1) 0.3s both',
        boxShadow: '0 8px 32px rgba(56,142,60,0.35)',
      }}>🐴</div>

      {/* Orbiting animals */}
      {[
        { emoji: '🫏', delay: '0s' },
        { emoji: '🐎', delay: '-1.2s' },
        { emoji: '🧒', delay: '-2.4s' },
      ].map((o, i) => (
        <div key={i} style={{
          position: 'absolute', top: '50%', left: '50%',
          marginTop: -16, marginLeft: -16,
          width: 32, height: 32,
          zIndex: 6, fontSize: 26,
          animation: `sa-orbit 3.6s linear ${o.delay} infinite`,
          transform: `rotate(${i * 120}deg) translateX(80px) rotate(-${i * 120}deg)`,
        }}>{o.emoji}</div>
      ))}

      {/* App name */}
      <div style={{
        position: 'absolute', top: '14%', left: 0, right: 0,
        textAlign: 'center', zIndex: 10,
      }}>
        <div style={{
          fontFamily: '"Baloo 2", sans-serif', fontWeight: 800,
          fontSize: 'clamp(44px, 9vw, 68px)', color: '#33691e', lineHeight: 1,
          animation: 'sa-bounceIn 0.8s cubic-bezier(.22,1,.36,1) 0.4s both',
        }}>{appName}</div>
        <div style={{
          fontFamily: '"Quicksand", sans-serif', fontWeight: 600,
          fontSize: 'clamp(16px, 3.5vw, 22px)', color: '#558b2f', marginTop: 6,
          animation: 'sa-fadeUp 0.6s ease 0.9s both',
        }}>{sub}</div>
      </div>

      {/* Loader */}
      <div style={{
        position: 'absolute', bottom: '7%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', gap: 10, zIndex: 10,
        animation: 'sa-fadeIn 0.4s ease 1.4s both',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 10, height: 10, borderRadius: '50%', background: '#388e3c',
            animation: `sa-bounce 0.8s ease-in-out ${i * 0.15}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

/* ── Hufspur ──────────────────────────────────────────────────── */
function HufspurTheme({ appName, subtitle }) {
  const [prints, setPrints] = useState([])
  const sub = subtitle || THEME_SUBTITLES.hufspur

  useEffect(() => {
    setPrints(Array.from({ length: 15 }, (_, i) => ({
      left: `${5 + Math.random() * 85}%`,
      top: `${5 + Math.random() * 80}%`,
      size: 18 + Math.random() * 22,
      rotate: Math.random() * 360,
      delay: `${i * 0.15}s`,
    })))
  }, [])

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: '#faf5ee',
    }}>
      {/* Scattered hoof prints */}
      {prints.map((p, i) => (
        <div key={i} style={{
          position: 'absolute', left: p.left, top: p.top,
          fontSize: p.size,
          transform: `rotate(${p.rotate}deg)`,
          animation: `sa-fadeIn 0.4s ease ${p.delay} both`,
          opacity: 0.45,
        }}>🐾</div>
      ))}

      {/* App name block */}
      <div style={{
        position: 'absolute', top: '50%', left: 0, right: 0,
        transform: 'translateY(-58%)', textAlign: 'center', zIndex: 10,
      }}>
        <div style={{
          fontFamily: '"DM Serif Display", Georgia, serif',
          fontSize: 'clamp(40px, 9vw, 64px)', color: '#4a3728', lineHeight: 1,
          animation: 'sa-fadeUp 0.7s cubic-bezier(.22,1,.36,1) 0.6s both',
        }}>{appName}</div>

        {/* Animated underline */}
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
          <div style={{
            height: 3, borderRadius: 2,
            background: 'linear-gradient(90deg, #5b7c5e, #81c784)',
            animation: 'sa-expand 0.7s ease 1.1s both',
          }} />
        </div>

        <div style={{
          fontFamily: '"Caveat", cursive', fontWeight: 600,
          fontSize: 'clamp(18px, 4vw, 26px)', color: '#8d6e63', marginTop: 14,
          animation: 'sa-fadeUp 0.6s ease 1s both',
        }}>{sub}</div>
      </div>

      {/* Hoof track loader */}
      <div style={{
        position: 'absolute', bottom: '8%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', gap: 8, zIndex: 10,
        animation: 'sa-fadeIn 0.4s ease 1.5s both',
      }}>
        {Array.from({ length: 5 }, (_, i) => (
          <span key={i} style={{
            fontSize: 16,
            animation: `sa-stepIn 0.35s ease ${i * 0.12}s both`,
          }}>🐾</span>
        ))}
      </div>
    </div>
  )
}

/* ── Stallgeflüster ───────────────────────────────────────────── */
function StallgefluesterTheme({ appName, subtitle }) {
  const [stars, setStars] = useState([])
  const [zs, setZs] = useState([])
  const sub = subtitle || THEME_SUBTITLES.stallgefluester

  useEffect(() => {
    setStars(Array.from({ length: 50 }, (_, i) => ({
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 70}%`,
      size: 2 + Math.random() * 3,
      delay: `${Math.random() * 3}s`,
      duration: `${1.5 + Math.random() * 2}s`,
    })))
    setZs([{ left: '52%', delay: '1.4s' }, { left: '58%', delay: '1.7s' }, { left: '64%', delay: '2.0s' }])
  }, [])

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: 'linear-gradient(180deg, #2d2438 0%, #4a3a5c 100%)',
    }}>
      {/* Stars */}
      {stars.map((s, i) => (
        <div key={i} style={{
          position: 'absolute', left: s.left, top: s.top,
          width: s.size, height: s.size, borderRadius: '50%', background: '#fff',
          animation: `sa-twinkle ${s.duration} ease-in-out ${s.delay} infinite`,
        }} />
      ))}

      {/* Moon */}
      <div style={{
        position: 'absolute', top: '8%', right: '8%', zIndex: 3,
        animation: 'sa-fadeIn 0.8s ease 0.3s both',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: '#ffe082', boxShadow: '0 0 30px 8px rgba(255,224,130,0.4)',
          position: 'relative',
        }}>
          <div style={{
            position: 'absolute', top: -4, right: -4,
            width: 52, height: 52, borderRadius: '50%',
            background: '#3b2f4a',
          }} />
        </div>
      </div>

      {/* Barn silhouette */}
      <div style={{
        position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: 220, zIndex: 4,
        animation: 'sa-fadeIn 0.7s ease 0.5s both',
      }}>
        {/* Roof */}
        <div style={{
          width: 0, height: 0,
          borderLeft: '110px solid transparent',
          borderRight: '110px solid transparent',
          borderBottom: '70px solid #1a1025',
          margin: '0 auto',
        }} />
        {/* Body */}
        <div style={{
          width: '100%', height: 120, background: '#1a1025',
          display: 'flex', alignItems: 'center', justifyContent: 'space-around',
          padding: '0 20px',
        }}>
          {/* Windows */}
          {[0, 1].map(i => (
            <div key={i} style={{
              width: 36, height: 36,
              background: 'rgba(255,193,7,0.15)',
              borderRadius: 4, border: '2px solid #3d2e10',
              boxShadow: '0 0 12px 4px rgba(255,193,7,0.25)',
              animation: `sa-pulse 2s ease-in-out ${i * 0.4}s infinite`,
            }} />
          ))}
        </div>
      </div>

      {/* App name */}
      <div style={{
        position: 'absolute', top: '30%', left: 0, right: 0,
        textAlign: 'center', zIndex: 10,
      }}>
        <div style={{
          fontFamily: '"Caveat", cursive', fontWeight: 700,
          fontSize: 'clamp(40px, 9vw, 62px)', color: '#fef3c7', lineHeight: 1,
          animation: 'sa-fadeUp 0.7s ease 0.7s both',
          textShadow: '0 2px 20px rgba(255,243,199,0.3)',
        }}>{appName}</div>
        <div style={{
          fontFamily: '"Quicksand", sans-serif', fontWeight: 500,
          fontSize: 'clamp(14px, 3vw, 20px)', color: '#d4b896', marginTop: 8,
          animation: 'sa-fadeUp 0.6s ease 1.1s both',
        }}>{sub}</div>
      </div>

      {/* Floating Z loader */}
      <div style={{
        position: 'absolute', bottom: '12%', left: 0, right: 0,
        height: 40, zIndex: 10,
      }}>
        {zs.map((z, i) => (
          <div key={i} style={{
            position: 'absolute', left: z.left, bottom: 0,
            fontFamily: '"Caveat", cursive', fontWeight: 700,
            fontSize: 24, color: '#fef3c7',
            animation: `sa-float 1.4s ease-in-out ${z.delay} infinite`,
          }}>z</div>
        ))}
      </div>
    </div>
  )
}

/* ── Main component ───────────────────────────────────────────── */
const THEMES = {
  hofblick: HofblickTheme,
  koppel: KoppelTheme,
  hufspur: HufspurTheme,
  stallgefluester: StallgefluesterTheme,
}

export default function StartupAnimation({ appName, animationTheme, subtitle, onDone, preview = false }) {
  const [phase, setPhase] = useState('in')   // 'in' | 'out' | 'done'

  useEffect(() => {
    if (preview) return
    const showTimer = setTimeout(() => setPhase('out'), 3200)
    const doneTimer = setTimeout(() => { setPhase('done'); onDone?.() }, 3700)
    return () => { clearTimeout(showTimer); clearTimeout(doneTimer) }
  }, [preview, onDone])

  const ThemeComponent = THEMES[animationTheme] ?? THEMES.hofblick

  return (
    <>
      <style>{KEYFRAMES}</style>
      <div style={{
        position: preview ? 'relative' : 'fixed',
        inset: 0, zIndex: 9999,
        opacity: phase === 'out' ? 0 : 1,
        transition: 'opacity 0.5s ease-out',
        pointerEvents: phase === 'out' ? 'none' : 'all',
        borderRadius: preview ? 16 : 0,
        overflow: 'hidden',
        width: '100%',
        height: preview ? '100%' : '100vh',
      }}>
        <ThemeComponent appName={appName} subtitle={subtitle} />
      </div>
    </>
  )
}
