import React, { useState } from 'react';
import { MOODS } from './data/moods';
import MoodCard from './components/MoodCard';
import ResultPanel from './components/ResultPanel';
import AuthWrapper from './components/AuthWrapper';
import './App.css';

function App() {
  const [selectedMood, setSelectedMood] = useState(null);

  const handleSelect = (mood) => {
    setSelectedMood((prev) => (prev?.id === mood.id ? null : mood));
  };

  return (
    <AuthWrapper>
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <h1 className="app-title">🎵 Seoul Diary Playlist Generator</h1>
          <p className="app-subtitle">
            무드를 선택하면 Suno 프롬프트, AI 이미지 프롬프트, 유튜브 메타데이터를 자동 생성합니다.
          </p>
        </div>
      </header>

      <main className="app-main">
        <section className="mood-section">
          <h2 className="section-title">무드 선택</h2>
          <p className="section-desc">원하는 채널 분위기를 선택하세요.</p>
          <div className="mood-grid">
            {MOODS.map((mood) => (
              <MoodCard
                key={mood.id}
                mood={mood}
                isSelected={selectedMood?.id === mood.id}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </section>

        {selectedMood && <ResultPanel mood={selectedMood} />}
      </main>

      <footer className="app-footer">
        <p>Seoul Diary Playlist · AI-powered by Suno & Midjourney</p>
      </footer>
    </div>
    </AuthWrapper>
  );
}

export default App;
