import { Route, Routes } from 'react-router-dom';

import { CatalogPage } from './pages/CatalogPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ToolPage } from './pages/ToolPage';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<CatalogPage />} />
      <Route path="/:slug" element={<ToolPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
