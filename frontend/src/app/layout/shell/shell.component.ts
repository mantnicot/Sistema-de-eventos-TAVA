import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { HeroVideoComponent } from '../hero-video/hero-video.component';
import { TavaContactFabComponent } from '../../shared/components/tava-contact-fab/tava-contact-fab.component';
import { TavaPopupComponent } from '../../shared/components/tava-popup/tava-popup.component';
import { SessionIdleService } from '../../core/services/session-idle.service';
import { ApiWarmupService } from '../../core/services/api-warmup.service';

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
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  private readonly site = inject(SiteSettingsService);
  private readonly router = inject(Router);
  private readonly idle = inject(SessionIdleService);
  private readonly warmup = inject(ApiWarmupService);
  private navSub?: Subscription;

  menuOpen = false;

  ngOnInit(): void {
    void this.warmup.wake();
    setTimeout(() => this.site.loadAppearance(), 800);
    this.idle.start();
    this.navSub = this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => this.closeMenu());
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
  }

  closeMenu(): void {
    this.menuOpen = false;
  }

  logout(): void {
    this.closeMenu();
    this.auth.logout();
  }
}
