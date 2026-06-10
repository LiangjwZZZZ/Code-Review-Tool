import { useEffect, useState } from 'react';
import { fetchLauncherConfig, saveLauncherConfig, shutdownServer } from '../api';
import type { LauncherConfigData } from '../api';

const navStyle: React.CSSProperties = {
  display: 'flex', gap: 16, alignItems: 'center', marginBottom: 24,
  padding: '10px 0', borderBottom: '1px solid #eee',
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 680, margin: '0 auto', padding: 32,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  card: { background: '#fff', border: '1px solid #e0e0e0', borderRadius: 10, padding: 24 },
  row: { display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' as const },
  field: { flex: 1, minWidth: 200 },
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: '#555', marginBottom: 4 },
  input: {
    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd',
    fontSize: 14, boxSizing: 'border-box' as const,
  },
  select: {
    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd',
    fontSize: 14, background: '#fff',
  },
  btn: {
    padding: '10px 24px', borderRadius: 6, border: 'none', fontSize: 15,
    fontWeight: 600, color: '#fff', backgroundColor: '#3498db', cursor: 'pointer',
  },
  navLink: {
    fontSize: 14, color: '#3498db', textDecoration: 'none', fontWeight: 500,
    cursor: 'pointer',
  },
};

export default function LauncherPage() {
  const [config, setConfig] = useState<LauncherConfigData>({
    api_key: '', model: 'deepseek-v4-flash', host: '127.0.0.1',
    port: 9090, repo_path: '.', commit_hash: '', api_type: 'deepseek',
    log_dir: '', repos: [], current_repo: '', global_branch: '', per_repo_branches: {},
    gerrit_username: '', gerrit_password: '', git_path: '',
  });
  useEffect(() => {
    fetchLauncherConfig().then(setConfig).catch(() => {});
  }, []);

  const handleSave = async () => {
    await saveLauncherConfig(config);
    window.location.href = '/timeline';
  };

  const handleShutdown = async () => {
    if (!window.confirm('确定要关闭 Review 服务吗？')) return;
    await shutdownServer();
  };

  const set = (key: keyof LauncherConfigData, value: string | number) =>
    setConfig((prev) => ({ ...prev, [key]: value }));

  return (
    <div style={styles.container}>
      <div style={navStyle}>
        <span style={{ fontSize: 18, fontWeight: 700 }}>设置</span>
        <a style={styles.navLink} href="/timeline">← 时间线</a>
      </div>

      <div style={styles.card}>
        <div style={styles.row}>
          <div style={styles.field}>
            <label style={styles.label}>API 类型</label>
            <select style={styles.select} value={config.api_type} onChange={(e) => set('api_type', e.target.value)}>
              <option value="deepseek">DeepSeek</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div style={{ ...styles.field, flex: 2 }}>
            <label style={styles.label}>API Key</label>
            <input style={styles.input} type="password" placeholder="sk-..." value={config.api_key} onChange={(e) => set('api_key', e.target.value)} />
          </div>
        </div>

        <div style={styles.row}>
          <div style={styles.field}>
            <label style={styles.label}>模型</label>
            <input style={styles.input} placeholder="deepseek-v4-flash" value={config.model} onChange={(e) => set('model', e.target.value)} />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Host</label>
            <input style={styles.input} value={config.host} onChange={(e) => set('host', e.target.value)} />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>端口</label>
            <input style={styles.input} type="number" value={config.port} onChange={(e) => set('port', Number(e.target.value))} />
          </div>
        </div>

        <div style={styles.row}>
          <div style={{ ...styles.field, flex: 2 }}>
            <label style={styles.label}>仓库路径</label>
            <input style={styles.input} placeholder=". (当前目录)" value={config.repo_path} onChange={(e) => set('repo_path', e.target.value)} />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Commit Hash (可选)</label>
            <input style={styles.input} placeholder="留空默认浏览" value={config.commit_hash} onChange={(e) => set('commit_hash', e.target.value)} />
          </div>
        </div>

        <div style={styles.row}>
          <div style={{ ...styles.field, flex: 3 }}>
            <label style={styles.label}>日志目录 (留空默认 ~/.review/logs/)</label>
            <input style={styles.input} placeholder="留空使用默认位置" value={config.log_dir} onChange={(e) => set('log_dir', e.target.value)} />
          </div>
        </div>

        <div style={styles.row}>
          <div style={{ ...styles.field, flex: 3 }}>
            <label style={styles.label}>Git 路径 (留空使用系统默认)</label>
            <input style={styles.input} placeholder="留空使用系统 git，或指定完整路径如 C:\cygwin\bin\git.exe" value={config.git_path || ''} onChange={(e) => set('git_path', e.target.value)} />
          </div>
        </div>

        <hr style={{ margin: '16px 0 20px', border: 'none', borderTop: '1px solid #eee' }} />
        <div style={{ fontSize: 13, fontWeight: 700, color: '#555', marginBottom: 12 }}>Gerrit 认证</div>
        <div style={styles.row}>
          <div style={styles.field}>
            <label style={styles.label}>Gerrit 用户名</label>
            <input style={styles.input} placeholder="your-username" value={config.gerrit_username || ''} onChange={(e) => set('gerrit_username', e.target.value)} />
          </div>
          <div style={{ ...styles.field, flex: 2 }}>
            <label style={styles.label}>Gerrit HTTP 密码</label>
            <input style={styles.input} type="password" placeholder="Gerrit → Settings → HTTP Credentials" value={config.gerrit_password || ''} onChange={(e) => set('gerrit_password', e.target.value)} />
          </div>
        </div>

        <button style={styles.btn} onClick={handleSave}>保存配置</button>

        <hr style={{ margin: '24px 0', border: 'none', borderTop: '1px solid #eee' }} />
        <button
          onClick={handleShutdown}
          style={{
            padding: '10px 24px', borderRadius: 6, border: 'none', fontSize: 14,
            fontWeight: 600, color: '#fff', backgroundColor: '#e74c3c', cursor: 'pointer',
          }}
        >关闭服务</button>
      </div>
    </div>
  );
}
