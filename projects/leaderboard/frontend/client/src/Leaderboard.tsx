import React, { useState, useEffect } from 'react';

interface User {
  email: string;
  score: number;
}

const Leaderboard: React.FC = () => {
  const [leaderboardData, setLeaderboardData] = useState<User[]>([]);
  const [gameData, setGameData] = useState<any>(null);

  useEffect(() => {
    fetch('/api/leaderboard')
      .then(response => response.json())
      .then(data => {
        if (data.ok) {
          setLeaderboardData(data.entries);
        }
      });
  }, []);

  useEffect(() => {
    fetch('/api/espn/game/basketball/nba/400878160')
      .then(response => response.json())
      .then(data => {
        setGameData(data);
      });
  }, []);

  return (
    <div>
      <h1>Leaderboard</h1>
      <table>
        <thead>
          <tr>
            <th>Player</th>
            <th>Total Score</th>
          </tr>
        </thead>
        <tbody>
          {leaderboardData.map(user => (
            <tr key={user.email}>
              <td>{user.email}</td>
              <td>{user.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {gameData && (
        <div>
          <h2>Game Data</h2>
          <pre>{JSON.stringify(gameData, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default Leaderboard;
