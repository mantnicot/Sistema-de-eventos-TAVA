import { Component, effect, inject, OnDestroy, signal } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';
import { randomPopupPhrase } from '../../../core/utils/theatrical-messages.util';

@Component({
  selector: 'tava-popup',
  standalone: true,
  templateUrl: './tava-popup.component.html',
  styleUrl: './tava-popup.component.scss',
})
export class TavaPopupComponent implements OnDestroy {
  readonly notify = inject(NotificationService);
  readonly rotatingPhrase = signal('');
  readonly roseSlots = [0, 1, 2, 3, 4, 5, 6, 7];

  private phraseTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    effect(() => {
      const visible = !!this.notify.state()?.visible;
      this.clearPhraseTimer();
      if (visible) {
        this.rotatingPhrase.set(randomPopupPhrase());
        this.phraseTimer = setInterval(() => {
          this.rotatingPhrase.set(randomPopupPhrase());
        }, 5000);
      }
    });
  }

  ngOnDestroy(): void {
    this.clearPhraseTimer();
  }

  confirm(): void {
    const s = this.notify.state();
    s?.onConfirm?.();
    this.notify.hide();
  }

  cancel(): void {
    this.notify.hide();
  }

  private clearPhraseTimer(): void {
    if (this.phraseTimer) {
      clearInterval(this.phraseTimer);
      this.phraseTimer = null;
    }
  }
}
