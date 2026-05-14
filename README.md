# Chaox Auth 🛡️

**Chaox Auth** es un proyecto escolar, centrado en el control de acceso de usuarios utilizando inteligencia artificial. Implementa bibliotecas como **MediaPipe** con modelos pre-entrenados (*tasks*) para reconocer rostros y gestos dinámicos en tiempo real, a través de los cuales se lleva un control de ingreso y registro. Además, el sistema protege las imágenes y privacidad del usuario utilizando cifrado local.

---

## Características Principales

*   **Doble Factor de Autenticación:** 
    *   **Paso 1:** Detección facial para asegurar que existe un humano frente a la cámara.
    *   **Paso 2:** Reconocimiento de gestos manuales dinámicos (Ej. *Pulgar Arriba, Palma Abierta, Victoria*), pre-configurados por el usuario.
*   **Cifrado Seguro:** Las evidencias de ingreso (tanto accesos exitosos como intentos fallidos) y las fotografías de perfil son cifradas mediante `cryptography` (Fernet) antes de ser guardadas en el disco local.
*   **Prevención de Fuerza Bruta:** Bloqueo temporal progresivo de cuentas tras múltiples intentos biométricos fallidos.
*   **Dashboard de Usuario:** Panel donde cada usuario puede observar su historial de ingresos detallado y ajustar sus gestos de seguridad.
*   **Panel de Administrador Global:** Visualización de todos los usuarios registrados, gráficas de accesos estadísticos y un mapa interactivo mundial simulado a partir de geolocalización de IPs.
*   **UI/UX Moderna:** Interfaz responsiva y estilizada impulsada por *Tailwind CSS*, con animaciones fluidas y soporte completo para modo Oscuro/Claro.

---

## 🛠️ Tecnologías Usadas (Stack)

*   **Backend:** Flask, SQLAlchemy
*   **IA & Visión Artificial:** MediaPipe (Vision Tasks), OpenCV.
*   **Seguridad:** Cryptography.
*   **Frontend:** HTML5, Tailwind CSS, Lucide Icons, Chart.js, jsVectorMap.

---

## 🚀 Instalación y Despliegue

Para conocer los pasos de clonación, entorno virtual, dependencias y configuración de las llaves secretas y modelos `.task` de MediaPipe, por favor revisa el archivo adjunto:

👉 **[install.txt](install.txt)**

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Eres libre de usarlo, modificarlo y distribuirlo de manera gratuita y comercial, siempre y cuando se incluya el aviso de copyright original. Revisa el archivo [LICENSE](LICENSE) para más detalles.
