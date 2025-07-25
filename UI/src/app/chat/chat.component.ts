import { Component, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ChatService } from '../services/chat-services';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent implements AfterViewInit {
  userMessage = '';
  messages: { sender: 'user' | 'bot'; text: string }[] = [];

  @ViewChild('chatBox') chatBox!: ElementRef<HTMLDivElement>;


  constructor(private chatService: ChatService) {}

  botReplyTimeout: any = null;
  isBotReplying = false;

  ngAfterViewInit() {
    this.scrollToBottom();
  }

  handleButtonClick() {
    if (this.isBotReplying) {
      this.stopReply();
    } else {
      this.sendMessageApi();
    }
  }

  sendMessage() {
    const message = this.userMessage.trim();
    if (!message || this.isBotReplying) return;

    this.messages.push({ sender: 'user', text: message });
    this.userMessage = '';
    this.scrollToBottom();

    this.isBotReplying = true;

    this.botReplyTimeout = setTimeout(() => {
      this.messages.push({
        sender: 'bot',
        text: 'How can I assist you with your appointment?'
      });
      this.isBotReplying = false;
      this.botReplyTimeout = null;
      this.scrollToBottom();
    }, 1000); // Simulate delay
  }

  stopReply() {
    if (this.botReplyTimeout) {
      clearTimeout(this.botReplyTimeout);
      this.botReplyTimeout = null;
      this.isBotReplying = false;
    }
  }

  scrollToBottom() {
    setTimeout(() => {
      const el = this.chatBox?.nativeElement;
      el.scrollTop = el.scrollHeight;
    }, 0);
  }

  sendMessageApi() {
    const message = this.userMessage.trim();
    if (!message || this.isBotReplying) return;
  
    this.messages.push({ sender: 'user', text: message });
    this.userMessage = '';
    this.scrollToBottom();
  
    this.isBotReplying = true;
  
    this.chatService.sendMessageToApi(message)
      .then(apiResponse => {
        // Assuming apiResponse.choices[0].message.content contains the bot's text for OpenAI
        const botReply = apiResponse.response || 'Sorry, I could not get a response.';
        this.messages.push({
          sender: 'bot',
          text: botReply
        });
        this.isBotReplying = false;
        this.scrollToBottom();
      })
      .catch(error => {
        console.error('Error fetching bot response:', error);
        this.messages.push({
          sender: 'bot',
          text: 'An error occurred. Please try again.'
        });
        this.isBotReplying = false;
        this.scrollToBottom();
      });
  }
  
}
