import { Component, inject } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'tava-popup',
  standalone: true,
  templateUrl: './tava-popup.component.html',
  styleUrl: './tava-popup.component.scss',
})
export class TavaPopupComponent {
  readonly notify = inject(NotificationService);

  confirm(): void {
    const s = this.notify.state();
    s?.onConfirm?.();
    this.notify.hide();
  }

  cancel(): void {
    this.notify.hide();
  }
}
