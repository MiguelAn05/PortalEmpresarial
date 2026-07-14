import { useState } from 'react'
import api from '../api.js'

export default function CambiarPasswordModal({ onClose }) {
  const [form, setForm] = useState({ password_actual: '', password_nueva: '', confirmar: '' })
  const [error, setError] = useState('')
  const [exito, setExito] = useState(false)
  const [enviando, setEnviando] = useState(false)

  const handleChange = (e) => { setForm({ ...form, [e.target.name]: e.target.value }); setError('') }

  const handleSubmit = async () => {
    if (form.password_nueva.length < 6) {
      setError('La nueva contraseña debe tener al menos 6 caracteres.')
      return
    }
    if (form.password_nueva !== form.confirmar) {
      setError('Las contraseñas nuevas no coinciden.')
      return
    }
    setEnviando(true)
    try {
      await api.post('/auth/cambiar-password', {
        password_actual: form.password_actual,
        password_nueva: form.password_nueva,
      })
      setExito(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo cambiar la contraseña.')
    } finally {
      setEnviando(false)
    }
  }

  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-[#D6E0F0] text-sm text-[#1A2B47] focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#D6E0F0]">
          <h2 className="font-bold text-[#0D2B5E]">Cambiar contraseña</h2>
          <button onClick={onClose} className="text-[#6B7EA8] hover:text-[#0D2B5E] text-xl">✕</button>
        </div>

        {exito ? (
          <div className="p-6 text-center">
            <div className="text-3xl mb-2">✅</div>
            <p className="text-sm font-semibold text-[#1A2B47] mb-4">Contraseña actualizada correctamente.</p>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-[#0D2B5E] hover:bg-[#1A4FA0] text-white text-sm font-bold transition"
            >
              Listo
            </button>
          </div>
        ) : (
          <div className="p-6 space-y-3">
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Contraseña actual</label>
              <input type="password" name="password_actual" value={form.password_actual} onChange={handleChange} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Nueva contraseña</label>
              <input type="password" name="password_nueva" value={form.password_nueva} onChange={handleChange} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1.5">Confirmar nueva contraseña</label>
              <input type="password" name="confirmar" value={form.confirmar} onChange={handleChange} className={inputCls} />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">{error}</div>
            )}

            <button
              onClick={handleSubmit}
              disabled={enviando || !form.password_actual || !form.password_nueva}
              className="w-full mt-2 px-4 py-2.5 rounded-lg bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] text-sm font-bold transition disabled:opacity-50"
            >
              {enviando ? 'Guardando...' : 'Guardar nueva contraseña'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
