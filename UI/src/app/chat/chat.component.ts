import { Component, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

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

  botReplyTimeout: any = null;
  isBotReplying = false;

  ngAfterViewInit() {
    this.scrollToBottom();
  }

  handleButtonClick() {
    if (this.isBotReplying) {
      this.stopReply();
    } else {
      this.sendMessage();
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
}
