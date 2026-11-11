import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import './not-found.css';
import './features.css';
import './showcase.css';
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
