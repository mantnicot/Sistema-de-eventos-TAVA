import { DecimalPipe } from '@angular/common';
import { Component, input } from '@angular/core';

@Component({
  selector: 'tava-ticket-preview',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './tava-ticket-preview.component.html',
  styleUrl: './tava-ticket-preview.component.scss',
})
export class TavaTicketPreviewComponent {
  readonly eventName = input.required<string>();
  readonly eventDate = input('');
  readonly eventTime = input('');
  readonly city = input('');
  readonly address = input('');
  readonly typeName = input('Entrada');
  readonly kind = input('individual');
  readonly price = input(0);
  readonly benefits = input<string | undefined>();
  readonly imageUrl = input<string | undefined>();
  readonly holderName = input('Nombre del asistente');

  kindLabel(): string {
    const map: Record<string, string> = {
      individual: 'Individual',
      grupal: 'Grupal',
      vip: 'VIP',
      promocional: 'Promocional',
      cortesia: 'Cortesía',
    };
    return map[this.kind()] ?? this.kind();
  }
}
