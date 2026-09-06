import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { createApplication } from './app/createApplication';
import { ErrorBoundary } from './shared/ui/ErrorBoundary';
import '@xyflow/react/dist/style.css';
import './shared/styles/app.css';

const application = createApplication();
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App store={application.store} />
    </ErrorBoundary>
  </StrictMode>,
);
if (import.meta.hot) import.meta.hot.dispose(application.dispose);
