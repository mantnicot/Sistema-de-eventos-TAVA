import { Component } from '@angular/core';

@Component({
  selector: 'tava-contact-fab',
  standalone: true,
  templateUrl: './tava-contact-fab.component.html',
  styleUrl: './tava-contact-fab.component.scss',
})
export class TavaContactFabComponent {
  open = false;

  readonly whatsappUrl =
    'https://wa.me/573003268095?text=' +
    encodeURIComponent('Hola TAVA Teatro, me gustaría obtener información sobre sus eventos.');

  readonly instagramUrl = 'https://www.instagram.com/tavateatro/';
  readonly improUrl = 'https://impro-gamma.vercel.app';
  readonly improLogoUrl = 'https://impro-gamma.vercel.app/icons/tava-logo.png';

  toggle(): void {
    this.open = !this.open;
  }
}
