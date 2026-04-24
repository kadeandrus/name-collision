import "@/App.css";
import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import AdminNameCollision from "@/pages/AdminNameCollision";

const Home = () => (
  <div className="min-h-screen bg-white text-zinc-950 font-sans px-6 md:px-12 py-12">
    <div className="max-w-4xl mx-auto">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">
        Internal Tools
      </div>
      <h1 className="text-4xl md:text-5xl font-semibold tracking-tight mb-4">
        Name Collision & Rarity Scoring
      </h1>
      <p className="text-sm text-zinc-600 max-w-xl mb-10">
        Estimate how many U.S. residents likely share a given first + last
        name, using SSA baby-name data (1941–2010) and U.S. Census 2010
        surnames.
      </p>
      <Link
        to="/admin/name-collision"
        data-testid="admin-link"
        className="inline-block bg-zinc-950 hover:bg-zinc-800 text-white text-xs uppercase tracking-[0.15em] px-8 py-3 transition-colors"
      >
        Open admin tool →
      </Link>
    </div>
  </div>
);

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/admin/name-collision" element={<AdminNameCollision />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
