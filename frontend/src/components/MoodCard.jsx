import React from 'react';

function MoodCard({ mood, isSelected, onSelect }) {
  return (
    <div
      className={`mood-card${isSelected ? ' selected' : ''}`}
      onClick={() => onSelect(mood)}
      style={{ '--accent': mood.color }}
    >
      <span className="mood-emoji">{mood.emoji}</span>
      <span className="mood-season-badge">{mood.season}</span>
      <h3 className="mood-kor">{mood.korName}</h3>
      <p className="mood-eng">{mood.engName}</p>
      <div className="mood-keywords">
        {mood.trendKeywords.map((kw) => (
          <span key={kw} className="keyword-tag">
            {kw}
          </span>
        ))}
      </div>
      <p className="mood-length">⏱ 권장 {mood.recommendedLength}</p>
    </div>
  );
}

export default MoodCard;
