// Barline: esqueleto da Etapa 0.
// Só abre uma janela escura vazia, para provar que o build para Windows funciona.
// A interface real entra na Etapa 3.

#include <juce_gui_basics/juce_gui_basics.h>

namespace
{
    const juce::Colour kBackground { 0xff111214 };
    const juce::Colour kTextPrimary { 0xfff2f2f3 };
    const juce::Colour kTextSecondary { 0xff8b8d93 };
}

class MainComponent final : public juce::Component
{
public:
    MainComponent()
    {
        setSize (900, 560);
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (kBackground);

        auto area = getLocalBounds().reduced (24);

        g.setColour (kTextPrimary);
        g.setFont (juce::FontOptions (32.0f, juce::Font::bold));
        g.drawText ("Barline", area.removeFromTop (48), juce::Justification::centred);

        g.setColour (kTextSecondary);
        g.setFont (juce::FontOptions (16.0f));
        g.drawText ("Solte uma pasta de stems aqui (em breve)", area, juce::Justification::centred);
    }
};

class BarlineApplication final : public juce::JUCEApplication
{
public:
    const juce::String getApplicationName() override    { return JUCE_APPLICATION_NAME_STRING; }
    const juce::String getApplicationVersion() override { return JUCE_APPLICATION_VERSION_STRING; }
    bool moreThanOneInstanceAllowed() override          { return true; }

    void initialise (const juce::String&) override
    {
        mainWindow = std::make_unique<MainWindow> (getApplicationName());
    }

    void shutdown() override
    {
        mainWindow = nullptr;
    }

    void systemRequestedQuit() override
    {
        quit();
    }

private:
    class MainWindow final : public juce::DocumentWindow
    {
    public:
        explicit MainWindow (const juce::String& name)
            : DocumentWindow (name, kBackground, DocumentWindow::allButtons)
        {
            setUsingNativeTitleBar (true);
            setContentOwned (new MainComponent(), true);
            setResizable (true, true);
            centreWithSize (getWidth(), getHeight());
            setVisible (true);
        }

        void closeButtonPressed() override
        {
            JUCEApplication::getInstance()->systemRequestedQuit();
        }

    private:
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainWindow)
    };

    std::unique_ptr<MainWindow> mainWindow;
};

START_JUCE_APPLICATION (BarlineApplication)
