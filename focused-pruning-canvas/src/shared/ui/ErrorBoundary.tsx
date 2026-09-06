import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: string | null }
> {
  state: { error: string | null } = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('画面の描画に失敗しました', error, info.componentStack);
  }
  render() {
    return this.state.error ? (
      <main className="recovery">
        <h1>画面を表示できませんでした</h1>
        <p>保存データは自動的に削除されません。</p>
        <pre>{this.state.error}</pre>
        <button onClick={() => location.reload()}>再読込</button>
      </main>
    ) : (
      this.props.children
    );
  }
}
