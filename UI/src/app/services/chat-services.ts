import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { lastValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root'
  
})
export class ChatService {
  private apiUrl = 'http://localhost:8000/chat/'; 

  constructor(private http: HttpClient) { }

  async sendMessageToApi(message: string, sessionId: string = ''): Promise<any> {
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
    });
    const body = {
      message: message,
      session_id: sessionId
    };
    try {
      const response = await lastValueFrom(this.http.post(this.apiUrl, body, { headers }));
      return response;
    } catch (error) {
      console.error('API call error:', error);
      throw error;
    }
  }

}
