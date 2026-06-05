import { Component, inject, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { HeroVideoComponent } from '../hero-video/hero-video.component';
import { TavaContactFabComponent } from '../../shared/components/tava-contact-fab/tava-contact-fab.component';
import { TavaPopupComponent } from '../../shared/components/tava-popup/tava-popup.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    TavaPopupComponent,
    TavaContactFabComponent,
    HeroVideoComponent,
  ],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly site = inject(SiteSettingsService);
  menuOpen = false;

  ngOnInit(): void {
    this.site.loadAppearance();
  }
}
