import { Component, inject, OnDestroy, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  buildWhatsappUrl,
  resolveTavoAction,
  resolveTavoFreeText,
  TAVO_WELCOME,
  TavoButton,
  TavoMessage,
} from './tavo-chat.logic';

const MIN_THINK_MS = 700;
const MIN_TOTAL_MS = 1000;
const CHAR_MS = 18;

@Component({
  selector: 'tava-chatbot',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './tava-chatbot.component.html',
  styleUrl: './tava-chatbot.component.scss',
})
export class TavaChatbotComponent implements OnDestroy {
  private readonly router = inject(Router);

  readonly open = signal(false);
  readonly showHint = signal(true);
  readonly draft = signal('');
  readonly messages = signal<TavoMessage[]>([]);
  readonly typing = signal(false);
  readonly busy = signal(false);

  private seq = 0;
  private lastUserText = '';
  private timers: ReturnType<typeof setTimeout>[] = [];
  private replyToken = 0;

  /** Logo oficial TAVA (siempre en /public). */
  readonly avatarUrl = '/logo-tava.png';

  ngOnDestroy(): void {
    this.clearTimers();
  }

  toggle(): void {
    const next = !this.open();
    this.open.set(next);
    if (next) {
      this.showHint.set(false);
      if (!this.messages().length) {
        void this.pushTavo(TAVO_WELCOME, [
          { id: 'buy', label: '🎟️ Comprar boletas' },
          { id: 'create', label: '📝 Crear / publicar evento' },
          { id: 'tickets', label: '🎫 Mis boletas / reclamar' },
          { id: 'faq', label: '❓ FAQ general' },
          { id: 'whatsapp', label: '💬 Hablar por WhatsApp' },
        ]);
      }
    } else {
      this.showHint.set(true);
    }
  }

  close(): void {
    this.open.set(false);
    this.showHint.set(true);
  }

  onButton(btn: TavoButton): void {
    if (this.busy()) return;
    this.pushUser(btn.label);
    if (btn.id === 'whatsapp' && this.lastUserText && !/whatsapp|hablar/i.test(this.lastUserText)) {
      this.openExternal(buildWhatsappUrl(this.lastUserText));
      const result = resolveTavoAction('whatsapp');
      void this.pushTavo(result.reply.text, result.reply.buttons);
      return;
    }
    if (btn.label.toLowerCase().includes('enviar esta duda')) {
      this.openExternal(buildWhatsappUrl(this.lastUserText || 'Necesito ayuda con TAVA.'));
      void this.pushTavo('Listo: abrí WhatsApp con tu duda. Gracias por confiar en TAVA 🎭', [
        { id: 'menu', label: '← Menú' },
        { id: 'whatsapp', label: 'WhatsApp de nuevo' },
      ]);
      return;
    }
    const result = resolveTavoAction(btn.id);
    if (btn.route && btn.label.toLowerCase().includes('ir al')) {
      void this.pushTavo(
        'Te llevo al panel. Si no tienes permiso de organizador, inicia sesión o pide el rol.',
        result.reply.buttons
      );
      void this.router.navigate([btn.route], btn.fragment ? { fragment: btn.fragment } : undefined);
      return;
    }
    void this.pushTavo(result.reply.text, result.reply.buttons);
    const route = btn.route || result.navigateTo;
    const fragment = btn.fragment || result.fragment;
    if (route) {
      void this.router.navigate([route], fragment ? { fragment } : undefined);
    }
    if (result.openWhatsapp) {
      this.openExternal(result.openWhatsapp);
    }
  }

  sendText(): void {
    if (this.busy()) return;
    const text = this.draft().trim();
    if (!text) return;
    this.draft.set('');
    this.lastUserText = text;
    this.pushUser(text);
    const result = resolveTavoFreeText(text);
    void this.pushTavo(result.reply.text, result.reply.buttons);
    if (result.navigateTo) {
      void this.router.navigate(
        [result.navigateTo],
        result.fragment ? { fragment: result.fragment } : undefined
      );
    }
    if (result.openWhatsapp) {
      this.openExternal(result.openWhatsapp);
    }
  }

  openWhatsappAlways(): void {
    const doubt = this.lastUserText || this.draft().trim() || 'Necesito ayuda con la plataforma TAVA.';
    this.openExternal(buildWhatsappUrl(doubt));
  }

  private pushUser(text: string): void {
    this.lastUserText = text;
    this.messages.update((list) => [
      ...list,
      { id: `u-${++this.seq}`, from: 'user', text },
    ]);
    this.scrollSoon();
  }

  private async pushTavo(text: string, buttons?: TavoButton[]): Promise<void> {
    this.clearTimers();
    const token = ++this.replyToken;
    this.busy.set(true);
    this.typing.set(true);
    this.scrollSoon();

    const started = Date.now();
    await this.wait(MIN_THINK_MS);
    if (token !== this.replyToken) {
      this.busy.set(false);
      this.typing.set(false);
      return;
    }

    this.typing.set(false);
    const id = `t-${++this.seq}`;
    this.messages.update((list) => [...list, { id, from: 'tavo', text: '', buttons: undefined }]);
    this.scrollSoon();

    const remainingMin = Math.max(0, MIN_TOTAL_MS - (Date.now() - started));
    const typeBudget = Math.max(text.length * CHAR_MS, remainingMin || MIN_THINK_MS);
    const steps = Math.max(1, Math.ceil(typeBudget / CHAR_MS));
    const step = Math.max(1, Math.ceil(text.length / steps));

    let i = 0;
    await new Promise<void>((resolve) => {
      const tick = () => {
        if (token !== this.replyToken) {
          resolve();
          return;
        }
        i = Math.min(text.length, i + step);
        const slice = text.slice(0, i);
        this.messages.update((list) =>
          list.map((m) => (m.id === id ? { ...m, text: slice } : m))
        );
        this.scrollSoon();
        if (i >= text.length) {
          resolve();
          return;
        }
        this.timers.push(setTimeout(tick, CHAR_MS));
      };
      tick();
    });

    if (token !== this.replyToken) {
      this.busy.set(false);
      return;
    }

    const elapsed = Date.now() - started;
    if (elapsed < MIN_TOTAL_MS) {
      await this.wait(MIN_TOTAL_MS - elapsed);
    }
    if (token !== this.replyToken) {
      this.busy.set(false);
      return;
    }

    this.messages.update((list) =>
      list.map((m) => (m.id === id ? { ...m, text, buttons } : m))
    );
    this.busy.set(false);
    this.scrollSoon();
  }

  private wait(ms: number): Promise<void> {
    return new Promise((resolve) => {
      this.timers.push(setTimeout(resolve, ms));
    });
  }

  private clearTimers(): void {
    for (const t of this.timers) clearTimeout(t);
    this.timers = [];
  }

  private openExternal(url: string): void {
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  private scrollSoon(): void {
    queueMicrotask(() => {
      const el = document.querySelector('.tavo-chat__messages');
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  trackMsg(_: number, m: TavoMessage): string {
    return m.id;
  }

  showCaret(m: TavoMessage): boolean {
    if (m.from !== 'tavo' || !this.busy() || m.buttons?.length) return false;
    const list = this.messages();
    return list.length > 0 && list[list.length - 1].id === m.id;
  }
}
