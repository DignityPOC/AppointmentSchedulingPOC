import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { lastValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root'
  
})
export class ChatService {
  private apiUrl = 'http://localhost:8000/chat/'; // Replace with your actual API endpoint

  private apiKey = '';
  private apiOpenAiUrl = '';

  constructor(private http: HttpClient) { }

  async sendMessageToApi(message: string): Promise<any> {
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
    });
    const body = {
      user_input: message,
      // Add other parameters required by your API, e.g., model, max_tokens
    };
    try {
      const response = await lastValueFrom(this.http.post(this.apiUrl, body, { headers }));
      return response;
    } catch (error) {
      console.error('API call error:', error);
      throw error;
    }
  }

  // async sendMessageToApi(message: string): Promise<any> {
  //   const headers = new HttpHeaders({
  //     'Content-Type': 'application/json',
  //     Authorization: `Bearer ${this.apiKey}`,
  //   });

  //   const body = {
  //     model: 'gpt-4o-mini', // or any supported model
  //     messages: [{ role: 'user', content: message }],
  //   };

  //   try {
  //     const response: any = await lastValueFrom(this.http.post(this.apiOpenAiUrl, body, { headers }));
  //    Extract the bot reply from response
  //     return response;
  //   } catch (error) {
  //     console.error('OpenAI API call error:', error);
  //     throw new Error('Failed to fetch response from OpenAI');
  //   }
  // }
}
