import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface UploadResult {
  url: string;
  path: string;
  filename: string;
  media_type: string;
  size: number;
}

@Injectable({ providedIn: 'root' })
export class MediaUploadService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  upload(file: File, kind: 'image' | 'video'): Observable<UploadResult> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<UploadResult>(`${this.base}/media/upload?kind=${kind}`, form);
  }
}
