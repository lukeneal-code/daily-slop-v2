import { Route, Routes } from 'react-router-dom';

import Footer from './components/Footer';
import Masthead from './components/Masthead';
import SectionNav from './components/SectionNav';
import ArticlePage from './pages/ArticlePage';
import FrontPage from './pages/FrontPage';
import SectionPage from './pages/SectionPage';

export default function App() {
  return (
    <div className="newspaper">
      <Masthead />
      <SectionNav />
      <main className="newspaper-main">
        <Routes>
          <Route path="/" element={<FrontPage />} />
          <Route path="/date/:date" element={<FrontPage />} />
          <Route path="/section/:slug" element={<SectionPage />} />
          <Route path="/article/:slug" element={<ArticlePage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
