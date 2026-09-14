import React from 'react';
import ReactDOM from 'react-dom/client';
import { LiveApp } from '@/app/LiveApp';
import './index.css';
const StudioApp = React.lazy(() => import('@/app/App').then(module => ({ default: module.App })));
const isStudio = ['/studio', '/callback'].includes(window.location.pathname);

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root was not found in the DOM.');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <React.Suspense fallback={<p>화면을 불러오는 중입니다.</p>}>
      {isStudio ? <StudioApp /> : <LiveApp />}
    </React.Suspense>
  </React.StrictMode>
);

// Register Service Worker for air-gapped intranet offline support
if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('Service worker registration failed:', err);
    });
  });
}
