import { useState } from 'react'
import api from '../api.js'
import { IconoCerrar, IconoCheck } from './Iconos.jsx'

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

  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-borde">
          <h2 className="font-bold text-acento-fuerte">Cambiar contraseña</h2>
          <button onClick={onClose} aria-label="Cerrar" className="w-8 h-8 flex items-center justify-center rounded-lg text-texto-3 hover:bg-superficie-2 hover:text-texto transition-colors duration-150"><IconoCerrar tam={16} /></button>
        </div>

        {exito ? (
          <div className="p-6 text-center">
            <div className="flex justify-center mb-3"><span className="w-11 h-11 rounded-full bg-positivo-bg text-positivo flex items-center justify-center"><IconoCheck tam={22} /></span></div>
            <p className="text-sm font-semibold text-texto mb-4">Contraseña actualizada correctamente.</p>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-acento-fuerte hover:bg-acento text-white text-sm font-bold transition"
            >
              Listo
            </button>
          </div>
        ) : (
          <div className="p-6 space-y-3">
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Contraseña actual</label>
              <input type="password" name="password_actual" value={form.password_actual} onChange={handleChange} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Nueva contraseña</label>
              <input type="password" name="password_nueva" value={form.password_nueva} onChange={handleChange} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1.5">Confirmar nueva contraseña</label>
              <input type="password" name="confirmar" value={form.confirmar} onChange={handleChange} className={inputCls} />
            </div>

            {error && (
              <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-3 py-2 text-sm text-negativo">{error}</div>
            )}

            <button
              onClick={handleSubmit}
              disabled={enviando || !form.password_actual || !form.password_nueva}
              className="w-full mt-2 px-4 py-2.5 rounded-lg bg-ambar hover:bg-ambar-claro text-acento-fuerte text-sm font-bold transition disabled:opacity-50"
            >
              {enviando ? 'Guardando...' : 'Guardar nueva contraseña'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
