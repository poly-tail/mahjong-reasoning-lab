import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OutlineLabel } from '../../src/features/outline/OutlinePanel';
import { isTextEditing } from '../../src/features/outline/OutlineKeyboard';

describe('C06–07 Japanese composition and editing keyboard', () => {
  it('composition events and native isComposing prevent Enter from creating a sibling', () => {
    const commit = vi.fn();
    render(<OutlineLabel label="考察" commit={commit} cancel={vi.fn()} />);
    const input = screen.getByRole('textbox', { name: '項目ラベル' });
    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: '考察中' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.keyDown(input, { key: 'Tab' });
    expect(commit).not.toHaveBeenCalled();
    fireEvent.compositionEnd(input);
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    expect(commit).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(commit).toHaveBeenCalledExactlyOnceWith('考察中', true);
  });
  it('Escape cancels without committing and text fields retain browser undo', () => {
    const commit = vi.fn(),
      cancel = vi.fn();
    render(<OutlineLabel label="元の名前" commit={commit} cancel={cancel} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '変更中' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    fireEvent.blur(input);
    expect(cancel).toHaveBeenCalledOnce();
    expect(commit).not.toHaveBeenCalled();
    expect(isTextEditing(input)).toBe(true);
    expect(isTextEditing(document.createElement('button'))).toBe(false);
  });
});
