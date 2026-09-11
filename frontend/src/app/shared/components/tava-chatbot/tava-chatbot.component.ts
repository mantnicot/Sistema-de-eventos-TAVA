import { Component, inject, OnDestroy, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { TavaEvent, TavaEventDetail } from '../../../core/models/event.model';
import { readEventsCache } from '../../../core/utils/events-cache.util';
import {
  buildWhatsappUrl,
  formatEventInfo,
  menuButtons,
  resolveTavoAction,
  resolveTavoFreeText,
  tavoContextFromUser,
  welcomeForRole,
  TavoButton,
  TavoEventBrief,
  TavoMessage,
  TavoUserContext,
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
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);

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
  private eventsCatalog: TavoEventBrief[] = [];
  private eventsLoaded = false;
  private lastMenuRole: string | null = null;

  /** Logo Tavo (máscara + headset). */
  readonly avatarUrl = '/tavo-avatar.png';

  private userCtx(): TavoUserContext {
    return tavoContextFromUser(this.auth.user());
  }

  ngOnDestroy(): void {
    this.clearTimers();
  }

  toggle(): void {
    const next = !this.open();
    this.open.set(next);
    if (next) {
      this.showHint.set(false);
      void this.ensureEvents();
      const ctx = this.userCtx();
      const roleKey = `${ctx.role}:${ctx.loggedIn}`;
      if (!this.messages().length || this.lastMenuRole !== roleKey) {
        this.messages.set([]);
        this.lastMenuRole = roleKey;
        void this.pushTavo(welcomeForRole(ctx.role), menuButtons(ctx));
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
    const ctx = this.userCtx();
    if (btn.id === 'whatsapp' && this.lastUserText && !/whatsapp|hablar/i.test(this.lastUserText)) {
      this.openExternal(buildWhatsappUrl(this.lastUserText));
      const result = resolveTavoAction('whatsapp', this.eventsCatalog, ctx);
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
    void this.ensureEvents().then(() => {
      const result = resolveTavoAction(btn.id, this.eventsCatalog, ctx);
      if (btn.route && btn.label.toLowerCase().includes('ir al')) {
        void this.pushTavo('Te llevo al panel.', result.reply.buttons);
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
    });
  }

  sendText(): void {
    if (this.busy()) return;
    const text = this.draft().trim();
    if (!text) return;
    this.draft.set('');
    this.lastUserText = text;
    this.pushUser(text);
    const ctx = this.userCtx();
    void this.ensureEvents().then(async () => {
      const result = resolveTavoFreeText(text, this.eventsCatalog, ctx);
      if (result.fetchEventId) {
        await this.replyWithEventPrices(result.fetchEventId);
      } else {
        await this.pushTavo(result.reply.text, result.reply.buttons);
      }
      if (result.navigateTo) {
        void this.router.navigate(
          [result.navigateTo],
          result.fragment ? { fragment: result.fragment } : undefined
        );
      }
      if (result.openWhatsapp) {
        this.openExternal(result.openWhatsapp);
      }
    });
  }

  private async ensureEvents(): Promise<void> {
    if (this.eventsLoaded && this.eventsCatalog.length) return;
    const cached = readEventsCache('', '');
    if (cached?.length) {
      this.eventsCatalog = cached.map((e) => this.toBrief(e));
      this.eventsLoaded = true;
      return;
    }
    try {
      const list = await firstValueFrom(this.api.get<TavaEvent[]>('/events'));
      this.eventsCatalog = (list ?? []).map((e) => this.toBrief(e));
      this.eventsLoaded = true;
    } catch {
      this.eventsCatalog = [];
    }
  }

  private toBrief(e: TavaEvent | TavaEventDetail): TavoEventBrief {
    const detail = e as TavaEventDetail;
    return {
      id: e.id,
      name: e.name,
      description: e.description,
      event_date: e.event_date,
      event_time: e.event_time,
      city: e.city,
      address: e.address,
      category: e.category,
      tickets_available: e.tickets_available,
      ticket_types: detail.ticket_types?.map((tt) => ({ name: tt.name, price: tt.price })),
    };
  }

  private async replyWithEventPrices(eventId: string): Promise<void> {
    try {
      const detail = await firstValueFrom(this.api.get<TavaEventDetail>(`/events/${eventId}`));
      const brief = this.toBrief(detail);
      const idx = this.eventsCatalog.findIndex((e) => e.id === eventId);
      if (idx >= 0) this.eventsCatalog[idx] = brief;
      else this.eventsCatalog.push(brief);
      await this.pushTavo(formatEventInfo(brief, true), [
        { id: 'buy_cartelera', label: 'Ver ficha', route: `/eventos/${eventId}` },
        { id: 'buy_how', label: 'Cómo comprar' },
        { id: 'menu', label: '← Menú' },
        { id: 'whatsapp', label: 'WhatsApp' },
      ]);
    } catch {
      await this.pushTavo('Abre la ficha del evento en cartelera para ver fechas, lugar y precios.', [
        { id: 'buy_cartelera', label: 'Abrir cartelera', route: '/eventos' },
        { id: 'menu', label: '← Menú' },
      ]);
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
