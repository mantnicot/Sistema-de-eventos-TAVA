import { Component, inject, signal } from '@angular/core';
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

@Component({
  selector: 'tava-chatbot',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './tava-chatbot.component.html',
  styleUrl: './tava-chatbot.component.scss',
})
export class TavaChatbotComponent {
  private readonly router = inject(Router);

  readonly open = signal(false);
  readonly showHint = signal(true);
  readonly draft = signal('');
  readonly messages = signal<TavoMessage[]>([]);
  private seq = 0;
  private lastUserText = '';

  readonly avatarUrl = '/tavo-avatar.svg';

  toggle(): void {
    const next = !this.open();
    this.open.set(next);
    if (next) {
      this.showHint.set(false);
      if (!this.messages().length) {
        this.pushTavo(TAVO_WELCOME, [
          { id: 'buy', label: '🎟️ Comprar boletas' },
          { id: 'create', label: '📝 Crear / publicar evento' },
          { id: 'tickets', label: '🎫 Mis boletas / reclamar' },
          { id: 'faq', label: '❓ FAQ general' },
          { id: 'whatsapp', label: '💬 Hablar por WhatsApp' },
        ]);
      }
    }
  }

  close(): void {
    this.open.set(false);
  }

  onButton(btn: TavoButton): void {
    this.pushUser(btn.label);
    if (btn.id === 'whatsapp' && this.lastUserText && !/whatsapp|hablar/i.test(this.lastUserText)) {
      this.openExternal(buildWhatsappUrl(this.lastUserText));
      const result = resolveTavoAction('whatsapp');
      this.pushTavo(result.reply.text, result.reply.buttons);
      return;
    }
    if (btn.label.toLowerCase().includes('enviar esta duda')) {
      this.openExternal(buildWhatsappUrl(this.lastUserText || 'Necesito ayuda con TAVA.'));
      this.pushTavo('Listo: abrí WhatsApp con tu duda. Gracias por confiar en TAVA 🎭', [
        { id: 'menu', label: '← Menú' },
        { id: 'whatsapp', label: 'WhatsApp de nuevo' },
      ]);
      return;
    }
    const result = resolveTavoAction(btn.id);
    // Si el botón es solo navegación con el mismo id de explicación, no repetir texto largo
    if (btn.route && btn.label.toLowerCase().includes('ir al')) {
      this.pushTavo('Te llevo al panel. Si no tienes permiso de organizador, inicia sesión o pide el rol.', result.reply.buttons);
      void this.router.navigate([btn.route], btn.fragment ? { fragment: btn.fragment } : undefined);
      return;
    }
    this.pushTavo(result.reply.text, result.reply.buttons);
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
    const text = this.draft().trim();
    if (!text) return;
    this.draft.set('');
    this.lastUserText = text;
    this.pushUser(text);
    const result = resolveTavoFreeText(text);
    this.pushTavo(result.reply.text, result.reply.buttons);
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

  private pushTavo(text: string, buttons?: TavoButton[]): void {
    this.messages.update((list) => [
      ...list,
      { id: `t-${++this.seq}`, from: 'tavo', text, buttons },
    ]);
    this.scrollSoon();
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
}
